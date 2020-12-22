# Copyright (c) Facebook, Inc. and its affiliates.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# Taken from https://raw.githubusercontent.com/facebookresearch/torchbeast/3f3029cf3d6d488b8b8f952964795f451a49048f/torchbeast/monobeast.py
# and modified slightly

import argparse
import logging
import os
import pprint
import threading
import time
import timeit
import traceback
import typing
import copy
import psutil

import torch
from torch import multiprocessing as mp
from torch import nn
from torch.nn import functional as F

from continual_rl.policies.impala.torchbeast.core import environment
from continual_rl.policies.impala.torchbeast.core import file_writer
from continual_rl.policies.impala.torchbeast.core import prof
from continual_rl.policies.impala.torchbeast.core import vtrace
from continual_rl.utils.utils import Utils


Buffers = typing.Dict[str, typing.List[torch.Tensor]]


class Monobeast():
    def __init__(self, model_flags, observation_space, action_space, policy_class):
        self._model_flags = model_flags

        # Moved some of the original Monobeast code into a setup function, to make class objects
        self.buffers, self.model, self.learner_model, self.optimizer, self.plogger, \
            self.logger, self.checkpointpath = self.setup(model_flags, observation_space, action_space, policy_class)

    def setup(self, model_flags, observation_space, action_space, policy_class):
        logging.basicConfig(
            format=(
                "[%(levelname)s:%(process)d %(module)s:%(lineno)d %(asctime)s] " "%(message)s"
            ),
            level=0,
        )

        if model_flags.xpid is None:
            model_flags.xpid = "torchbeast-%s" % time.strftime("%Y%m%d-%H%M%S")

        plogger = file_writer.FileWriter(
            xpid=model_flags.xpid, xp_args=model_flags.__dict__, rootdir=model_flags.savedir
        )
        logger = logging.getLogger("logfile")

        checkpointpath = os.path.expandvars(
            os.path.expanduser("%s/%s/%s" % (model_flags.savedir, model_flags.xpid, "model.tar"))
        )

        if model_flags.num_buffers is None:  # Set sensible default for num_buffers.
            model_flags.num_buffers = max(2 * model_flags.num_actors, model_flags.batch_size)
        if model_flags.num_actors >= model_flags.num_buffers:
            raise ValueError("num_buffers should be larger than num_actors")
        if model_flags.num_buffers < model_flags.batch_size:
            raise ValueError("num_buffers should be larger than batch_size")

        model_flags.device = None
        if not model_flags.disable_cuda and torch.cuda.is_available():
            logging.info("Using CUDA.")
            model_flags.device = torch.device("cuda")
        else:
            logging.info("Not using CUDA.")
            model_flags.device = torch.device("cpu")

        model = policy_class(observation_space, action_space, model_flags.use_lstm)
        buffers = self.create_buffers(model_flags, observation_space.shape, model.num_actions)

        model.share_memory()

        learner_model = policy_class(
            observation_space, action_space, model_flags.use_lstm
        ).to(device=model_flags.device)

        optimizer = torch.optim.RMSprop(
            learner_model.parameters(),
            lr=model_flags.learning_rate,
            momentum=model_flags.momentum,
            eps=model_flags.epsilon,
            alpha=model_flags.alpha,
        )

        return buffers, model, learner_model, optimizer, plogger, logger, checkpointpath

    def compute_baseline_loss(self, advantages):
        return 0.5 * torch.sum(advantages ** 2)

    def compute_entropy_loss(self, logits):
        """Return the entropy loss, i.e., the negative entropy of the policy."""
        policy = F.softmax(logits, dim=-1)
        log_policy = F.log_softmax(logits, dim=-1)
        return torch.sum(policy * log_policy)

    def compute_policy_gradient_loss(self, logits, actions, advantages):
        cross_entropy = F.nll_loss(
            F.log_softmax(torch.flatten(logits, 0, 1), dim=-1),
            target=torch.flatten(actions, 0, 1),
            reduction="none",
        )
        cross_entropy = cross_entropy.view_as(advantages)
        return torch.sum(cross_entropy * advantages.detach())

    def act(
            self,
            model_flags,
            task_flags,
            actor_index: int,
            free_queue: mp.SimpleQueue,
            full_queue: mp.SimpleQueue,
            model: torch.nn.Module,
            buffers: Buffers,
            initial_agent_state_buffers,
    ):
        try:
            logging.info("Actor %i started.", actor_index)
            timings = prof.Timings()  # Keep track of how fast things are.

            gym_env, seed = Utils.make_env(task_flags.env_spec, create_seed=True)
            self.logger.info(f"Environment and libraries setup with seed {seed}")

            # TODO: remove (just not deleting functional code from monobeast quite yet)
            #seed = actor_index ^ int.from_bytes(os.urandom(4), byteorder="little")
            #gym_env.seed(seed)

            env = environment.Environment(gym_env)
            env_output = env.initial()
            agent_state = model.initial_state(batch_size=1)
            agent_output, unused_state = model(env_output, agent_state)
            while True:
                index = free_queue.get()
                if index is None:
                    break

                # Write old rollout end.
                for key in env_output:
                    buffers[key][index][0, ...] = env_output[key]
                for key in agent_output:
                    buffers[key][index][0, ...] = agent_output[key]
                for i, tensor in enumerate(agent_state):
                    initial_agent_state_buffers[index][i][...] = tensor

                # Do new rollout.
                for t in range(model_flags.unroll_length):
                    timings.reset()

                    with torch.no_grad():
                        agent_output, agent_state = model(env_output, agent_state)

                    timings.time("model")

                    env_output = env.step(agent_output["action"])

                    timings.time("step")

                    for key in env_output:
                        buffers[key][index][t + 1, ...] = env_output[key]
                    for key in agent_output:
                        buffers[key][index][t + 1, ...] = agent_output[key]

                    timings.time("write")
                full_queue.put(index)

            if actor_index == 0:
                logging.info("Actor %i: %s", actor_index, timings.summary())

        except KeyboardInterrupt:
            pass  # Return silently.
        except Exception as e:
            logging.error("Exception in worker process %i", actor_index)
            traceback.print_exc()
            print()
            raise e

    def get_batch(
            self,
            flags,
            free_queue: mp.SimpleQueue,
            full_queue: mp.SimpleQueue,
            buffers: Buffers,
            initial_agent_state_buffers,
            timings,
            lock=threading.Lock(),
    ):
        with lock:
            timings.time("lock")
            indices = [full_queue.get() for _ in range(flags.batch_size)]
            timings.time("dequeue")
        batch = {
            key: torch.stack([buffers[key][m] for m in indices], dim=1) for key in buffers
        }
        initial_agent_state = (
            torch.cat(ts, dim=1)
            for ts in zip(*[initial_agent_state_buffers[m] for m in indices])
        )
        timings.time("batch")
        for m in indices:
            free_queue.put(m)
        timings.time("enqueue")
        batch = {k: t.to(device=flags.device, non_blocking=True) for k, t in batch.items()}
        initial_agent_state = tuple(
            t.to(device=flags.device, non_blocking=True) for t in initial_agent_state
        )
        timings.time("device")
        return batch, initial_agent_state

    def learn(
            self,
            flags,
            actor_model,
            model,
            batch,
            initial_agent_state,
            optimizer,
            scheduler,
            lock=threading.Lock(),  # noqa: B008
    ):
        """Performs a learning (optimization) step."""
        with lock:
            learner_outputs, unused_state = model(batch, initial_agent_state)

            # Take final value function slice for bootstrapping.
            bootstrap_value = learner_outputs["baseline"][-1]

            # Move from obs[t] -> action[t] to action[t] -> obs[t].
            batch = {key: tensor[1:] for key, tensor in batch.items()}
            learner_outputs = {key: tensor[:-1] for key, tensor in learner_outputs.items()}

            rewards = batch["reward"]
            if flags.reward_clipping == "abs_one":
                clipped_rewards = torch.clamp(rewards, -1, 1)
            elif flags.reward_clipping == "none":
                clipped_rewards = rewards

            discounts = (~batch["done"]).float() * flags.discounting

            vtrace_returns = vtrace.from_logits(
                behavior_policy_logits=batch["policy_logits"],
                target_policy_logits=learner_outputs["policy_logits"],
                actions=batch["action"],
                discounts=discounts,
                rewards=clipped_rewards,
                values=learner_outputs["baseline"],
                bootstrap_value=bootstrap_value,
            )

            pg_loss = self.compute_policy_gradient_loss(
                learner_outputs["policy_logits"],
                batch["action"],
                vtrace_returns.pg_advantages,
            )
            baseline_loss = flags.baseline_cost * self.compute_baseline_loss(
                vtrace_returns.vs - learner_outputs["baseline"]
            )
            entropy_loss = flags.entropy_cost * self.compute_entropy_loss(
                learner_outputs["policy_logits"]
            )

            total_loss = pg_loss + baseline_loss + entropy_loss

            episode_returns = batch["episode_return"][batch["done"]]
            stats = {
                "episode_returns": tuple(episode_returns.cpu().numpy()),
                "mean_episode_return": torch.mean(episode_returns).item(),
                "total_loss": total_loss.item(),
                "pg_loss": pg_loss.item(),
                "baseline_loss": baseline_loss.item(),
                "entropy_loss": entropy_loss.item(),
            }

            optimizer.zero_grad()
            total_loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), flags.grad_norm_clipping)
            optimizer.step()
            scheduler.step()

            actor_model.load_state_dict(model.state_dict())
            return stats

    def create_buffers(self, flags, obs_shape, num_actions) -> Buffers:
        T = flags.unroll_length
        specs = dict(
            frame=dict(size=(T + 1, *obs_shape), dtype=torch.uint8),
            reward=dict(size=(T + 1,), dtype=torch.float32),
            done=dict(size=(T + 1,), dtype=torch.bool),
            episode_return=dict(size=(T + 1,), dtype=torch.float32),
            episode_step=dict(size=(T + 1,), dtype=torch.int32),
            policy_logits=dict(size=(T + 1, num_actions), dtype=torch.float32),
            baseline=dict(size=(T + 1,), dtype=torch.float32),
            last_action=dict(size=(T + 1,), dtype=torch.int64),
            action=dict(size=(T + 1,), dtype=torch.int64),
        )
        buffers: Buffers = {key: [] for key in specs}
        for _ in range(flags.num_buffers):
            for key in buffers:
                buffers[key].append(torch.empty(**specs[key]).share_memory_())
        return buffers

    def train(self, task_flags):  # pylint: disable=too-many-branches, too-many-statements
        T = self._model_flags.unroll_length
        B = self._model_flags.batch_size

        def lr_lambda(epoch):
            return 1 - min(epoch * T * B, task_flags.total_steps) / task_flags.total_steps

        # TODO: check that this does what's expected if the lr_lambda changes but optimizer does not
        scheduler = torch.optim.lr_scheduler.LambdaLR(self.optimizer, lr_lambda)

        # Add initial RNN state.
        initial_agent_state_buffers = []
        for _ in range(self._model_flags.num_buffers):
            state = self.model.initial_state(batch_size=1)
            for t in state:
                t.share_memory_()
            initial_agent_state_buffers.append(state)

        # Setup actor processes and kick them off
        actor_processes = []
        ctx = mp.get_context("fork")
        free_queue = ctx.SimpleQueue()
        full_queue = ctx.SimpleQueue()

        for i in range(self._model_flags.num_actors):
            actor = ctx.Process(
                target=self.act,
                args=(
                    self._model_flags,
                    task_flags,
                    i,
                    free_queue,
                    full_queue,
                    self.model,
                    self.buffers,
                    initial_agent_state_buffers,
                ),
            )
            actor.start()
            actor_processes.append(actor)

        stat_keys = [
            "total_loss",
            "mean_episode_return",
            "pg_loss",
            "baseline_loss",
            "entropy_loss",
        ]
        self.logger.info("# Step\t%s", "\t".join(stat_keys))

        step, stats = 0, {}

        def batch_and_learn(i, lock=threading.Lock()):
            """Thread target for the learning process."""
            nonlocal step, stats
            timings = prof.Timings()
            while step < task_flags.total_steps:
                timings.reset()
                batch, agent_state = self.get_batch(
                    self._model_flags,
                    free_queue,
                    full_queue,
                    self.buffers,
                    initial_agent_state_buffers,
                    timings,
                )
                stats = self.learn(
                    self._model_flags, self.model, self.learner_model, batch, agent_state, self.optimizer, scheduler
                )
                timings.time("learn")
                with lock:
                    to_log = dict(step=step)
                    to_log.update({k: stats[k] for k in stat_keys})
                    self.plogger.log(to_log)
                    step += T * B

            if i == 0:
                logging.info("Batch and learn: %s", timings.summary())

        for m in range(self._model_flags.num_buffers):
            free_queue.put(m)

        threads = []
        for i in range(self._model_flags.num_learner_threads):
            thread = threading.Thread(
                target=batch_and_learn, name="batch-and-learn-%d" % i, args=(i,)
            )
            thread.start()
            threads.append(thread)

        def checkpoint():
            if self._model_flags.disable_checkpoint:
                return
            logging.info("Saving checkpoint to %s", self.checkpointpath)
            torch.save(
                {
                    "model_state_dict": self.model.state_dict(),
                    "optimizer_state_dict": self.optimizer.state_dict(),
                    "scheduler_state_dict": scheduler.state_dict(),
                    "model_flags": vars(self._model_flags),
                    "task_flags": vars(task_flags)
                },
                self.checkpointpath,
            )

        timer = timeit.default_timer
        last_returned_step = None
        try:
            last_checkpoint_time = timer()
            while step < task_flags.total_steps:
                start_step = step
                start_time = timer()
                time.sleep(5)

                if timer() - last_checkpoint_time > 10 * 60:  # Save every 10 min.
                    checkpoint()
                    last_checkpoint_time = timer()

                # Copy right away, because there's a race where stats can get re-set and then certain things set below
                # will be missing (eg "step")
                stats_to_return = copy.deepcopy(stats)

                sps = (step - start_step) / (timer() - start_time)
                if stats_to_return.get("episode_returns", None):
                    mean_return = (
                            "Return per episode: %.1f. " % stats_to_return["mean_episode_return"]
                    )
                else:
                    mean_return = ""
                total_loss = stats_to_return.get("total_loss", float("inf"))
                logging.info(
                    "Steps %i @ %.1f SPS. Loss %f. %sStats:\n%s",
                    step,
                    sps,
                    total_loss,
                    mean_return,
                    pprint.pformat(stats_to_return),
                )
                stats_to_return["step"] = step

                if last_returned_step is None or last_returned_step != step:
                    last_returned_step = step

                    # The actors will keep going unless we pause them, so...do that.
                    for actor in actor_processes:
                        psutil.Process(actor.pid).suspend()

                    yield stats_to_return

                    # Ensure everything is set back up to train
                    self.model.train()
                    self.learner_model.train()

                    # Resume the actors
                    for actor in actor_processes:
                        psutil.Process(actor.pid).resume()
                    
        except KeyboardInterrupt:
            return  # Try joining actors then quit.
        else:
            for thread in threads:
                thread.join()
            logging.info("Learning finished after %d steps.", step)
        finally:
            for _ in range(self._model_flags.num_actors):
                free_queue.put(None)
            for actor in actor_processes:
                actor.join(timeout=1)

        checkpoint()
        self.plogger.close()

    def test(self, task_flags, num_episodes: int = 10):
        gym_env, seed = Utils.make_env(task_flags.env_spec, create_seed=True)
        self.logger.info(f"Environment and libraries setup with seed {seed}")

        env = environment.Environment(gym_env)
        self.model.eval()

        # TODO: implement load()
        #checkpoint = torch.load(self.checkpointpath, map_location="cpu")
        #self.model.load_state_dict(checkpoint["model_state_dict"])

        observation = env.initial()
        returns = []

        while len(returns) < num_episodes:
            if task_flags.mode == "test_render":
                env.gym_env.render()
            agent_outputs = self.model(observation)
            policy_outputs, _ = agent_outputs
            observation = env.step(policy_outputs["action"])
            if observation["done"].item():
                returns.append(observation["episode_return"].item())
                logging.info(
                    "Episode ended after %d steps. Return: %.1f",
                    observation["episode_step"].item(),
                    observation["episode_return"].item(),
                )
        env.close()
        logging.info(
            "Average returns over %i steps: %.1f", num_episodes, sum(returns) / len(returns)
        )
