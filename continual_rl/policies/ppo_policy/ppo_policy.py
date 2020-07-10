import torch
from torch_ac.algos.ppo import PPOAlgo
from torch_ac.utils.dictlist import DictList
import numpy as np
from continual_rl.policies.policy_base import PolicyBase
from continual_rl.policies.ppo_policy.ppo_policy_config import PPOPolicyConfig
from continual_rl.policies.ppo_policy.ppo_info_to_store import PPOInfoToStoreBatch
from continual_rl.experiments.environment_runners.environment_runner_batch import EnvironmentRunnerBatch
from continual_rl.policies.ppo_policy.actor_critic_model import ActorCritic


class PPOParent(PPOAlgo):
    """
    We only want the function update_parameters on PPOAlgo not the abilities of its base class, so create a fake
    "self" with which to call update_parameters
    """
    def __init__(self, config, model):
        # Intentionally not calling super() because I do not want the normal initialization to be executed
        # Specifically, PPOAlgo's init calls BaseAlgo's init which initializes the environments. Since Policy is
        # intended to be isolated from the envs, I override like this.

        self.clip_eps = config.clip_eps
        self.epochs = config.epochs
        self.batch_size = config.batch_size
        self.recurrence = 1  # Number of timesteps over which the gradient is propagated. Recurrency not currently supported.
        self.optimizer = torch.optim.Adam(model.parameters(), lr=config.learning_rate, eps=config.adam_eps)
        self.acmodel = model
        self.entropy_coef = config.entropy_coef
        self.value_loss_coef = config.value_loss_coef
        self.max_grad_norm = config.max_grad_norm
        self.num_frames_per_proc = config.timesteps_per_collection
        self.num_frames = self.num_frames_per_proc * config.num_parallel_envs

        # Internal counter
        self.batch_num = 0


class PPOPolicy(PolicyBase):
    """
    Basically a wrapper around torch-ac's implementation of PPO
    """
    def __init__(self, config: PPOPolicyConfig, observation_size, action_sizes):
        super().__init__()
        self._config = config
        self._action_sizes = action_sizes

        # For this current simple implementation we just use the maximum action for our network, and extract the
        # subset necessary for a given task. The natural alternative is to have several different heads, one per
        # task.
        common_action_size = np.array(list(action_sizes.values())).max()

        # Due to the manipulation we do in compute_action, the observation_size is not exactly as input
        # Note that observation size does not include batch size
        observation_size = [observation_size[0] * observation_size[1], *observation_size[2:]]
        self._model = ActorCritic(observation_space=observation_size, action_space=common_action_size)
        self._ppo_trainer = PPOParent(config, self._model)

    def get_environment_runner(self):
        runner = EnvironmentRunnerBatch(policy=self, num_parallel_envs=self._config.num_parallel_envs,
                                        timesteps_per_collection=self._config.timesteps_per_collection)
        return runner

    def compute_action(self, observation, task_id):
        task_action_count = self._action_sizes[task_id]

        # The input observation is [batch, time, C, W, H]
        # We convert to [batch, time * C, W, H]
        compacted_observation = observation.view(observation.shape[0], -1, *observation.shape[3:])

        # Collect the data and generate the action
        action_distribution, values = self._model(compacted_observation, task_action_count)
        actions = action_distribution.sample()
        log_probs = action_distribution.log_prob(actions)

        info_to_store = PPOInfoToStoreBatch(compacted_observation, actions, values, log_probs, task_action_count)

        return actions, info_to_store

    def train(self, storage_buffer):
        # Fake "self" to override the need to pass envs and such to PPOAlgo
        experiences = self._convert_to_ppo_experiences(storage_buffer)

        # PPOAlgo assumes the model forward only accepts observation, so doing this for now
        task_action_count = storage_buffer[0].task_action_count
        self._model.set_task_action_count(task_action_count)

        logs = self._ppo_trainer.update_parameters(experiences)

        # Would rather fail fast if something bad happens than to use the wrong action_count somehow
        self._model.set_task_action_count(None)

        print(logs)

    def save(self, output_path_dir, task_id, task_total_steps):
        pass

    def load(self, model_path):
        pass

    def _compute_advantages(self, info_to_stores):
        """
        Input should be a list of info_to_stores in order by time (0..T) all for the same environment.
        """
        # Compute the predicted value of the last entry
        with torch.no_grad():
            _, next_value = self._model(info_to_stores[-1].observation.unsqueeze(0), info_to_stores[-1].task_action_count)
            next_value = next_value.squeeze(0)  # Remove the batch

        next_advantage = 0

        # The final output container for the computed advantages, in the same order as info_to_stores
        advantages = [None for _ in range(len(info_to_stores))]

        for entry_id, info_entry in reversed(list(enumerate(info_to_stores))):
            if info_entry.done:
                next_value = 0
                next_advantage = 0

            delta = info_entry.reward + self._config.discount * next_value - info_entry.value
            advantages[entry_id] = delta + self._config.discount * self._config.gae_lambda * next_advantage

        return advantages

    def _convert_to_ppo_experiences(self, storage_buffer):
        """
        Format the experiences collected in the form expected by torch_ac
        """
        # storage_buffer contains timesteps_collected_per_proc entries of PPOInfoToStoreBatch
        # Group the data instead by environment, which is more meaningful
        env_sorted_info_to_stores = [info_to_store.regroup_by_env() for info_to_store in storage_buffer]
        condensed_env_sorted = list(zip(*env_sorted_info_to_stores))

        all_observations = []
        all_actions = []
        all_values = []
        all_rewards = []
        all_advantages = []
        all_log_probs = []

        for env_data in condensed_env_sorted:
            all_observations.append([entry.observation for entry in env_data])
            all_actions.append([entry.action for entry in env_data])
            all_values.append([entry.value for entry in env_data])
            all_rewards.append([entry.reward for entry in env_data])
            all_advantages.append(self._compute_advantages(env_data))
            all_log_probs.append([entry.log_prob for entry in env_data])

        # torch_ac's experiences expect [num_envs, timesteps_per_collection] -> [num_envs * timesteps_per_collection]
        # Thanks to torch_ac for this PPO implementation - LICENSE available as a sibling to this file
        experiences = DictList()
        experiences.obs = torch.stack([all_observations[j][i]
                                       for j in range(self._config.num_parallel_envs)
                                       for i in range(self._config.timesteps_per_collection)])
        experiences.action = torch.Tensor(all_actions).reshape(-1)
        experiences.value = torch.Tensor(all_values).reshape(-1)
        experiences.reward = torch.Tensor(all_rewards).reshape(-1)
        experiences.advantage = torch.Tensor(all_advantages).reshape(-1)
        experiences.log_prob = torch.Tensor(all_log_probs).reshape(-1)

        experiences.returnn = experiences.value + experiences.advantage

        return experiences
