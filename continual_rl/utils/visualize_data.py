import argparse
import os
from glob import glob
import pandas as pd
import numpy as np
import collections
import copy
import cloudpickle as pickle
from scipy.stats import sem

import plotly.graph_objects as go

# see https://github.com/plotly/Kaleido/issues/101
import plotly.io as pio
pio.kaleido.scope.mathjax = None  # Prevents a weird "Loading MathJax" artifact in rendering the pdf


USE_ISOLATED_ZSFT = True
USE_ISOLATED_FORGETTING = False
USE_CACHE = False #True
SAVE_IN_CACHE = True


TASKS_ATARI = {
    "0-SpaceInvaders": dict(i=0, y_range=[0, 4e3], yaxis_dtick=1e3, train_regions=[[0, 50e6], [300e6, 350e6]], showlegend=False),
    "1-Krull": dict(i=1, y_range=[0, 1e4], yaxis_dtick=2e3, train_regions=[[50e6, 100e6], [350e6, 400e6]], showlegend=False),
    "2-BeamRider": dict(i=2, y_range=[0, 1e4], yaxis_dtick=2e3, train_regions=[[100e6, 150e6], [400e6, 450e6]], showlegend=True),
    "3-Hero": dict(i=3, y_range=[0, 5e4], yaxis_dtick=1e4, train_regions=[[150e6, 200e6], [450e6, 500e6]], showlegend=False),
    "4-StarGunner": dict(i=4, y_range=[0, 10e4], yaxis_dtick=2e4, train_regions=[[200e6, 250e6], [500e6, 550e6]], showlegend=False),
    "5-MsPacman": dict(i=5, y_range=[0, 4e3], yaxis_dtick=1e3, train_regions=[[250e6, 300e6], [550e6, 600e6]], showlegend=True),
}


MODELS_ATARI = {
    "IMPALA": dict(
        name='impala',
        runs=[f'impala{i}' for i in range(5)],
        # color='rgba(64, 132, 133, 1)',
        color='rgba(77, 102, 133, 1)',
        color_alpha=0.2,
    ),
    "EWC": dict(
        name='ewc',
        runs=[f'ewc{i}' for i in range(5)],
        color='rgba(214, 178, 84, 1)',
        color_alpha=0.2,
    ),
    "ONLINE EWC": dict(
        name='online ewc',
        runs=[f'onlineewc{i}' for i in range(5)],
        color='rgba(106, 166, 110, 1)',
        color_alpha=0.2,
    ),
    "P&C": dict(
        name='pnc',
        runs=['pnc0', 'pnc1', 'pnc2', 'pnc3_last1Mlost', 'pnc4'],
        # color='rgba(152, 52, 48, 1)',
        color='rgba(152, 67, 63, 1)',
        color_alpha=0.2,
    ),
    "CLEAR": dict(
        name='clear',
        runs=['clear0', 'clear1', 'clear2', 'clear5', 'clear8'],
        # color='rgba(212, 162, 217, 1)',
        color='rgba(210, 140, 217, 1)',
        color_alpha=0.2,
    ),
}
ATARI = dict(
    models=MODELS_ATARI,
    tasks=TASKS_ATARI,
    num_cycles=2,
    num_cycles_for_forgetting=1,
    num_task_steps=50e6,
    grid_size=[2, 3],
    which_exp='atari',
    rolling_mean_count=20,
    filter='ma',
    xaxis_tickvals=list(np.arange(0, 600e6 + 1, 300e6)),
    cache_dir='tmp/cache/data_pkls/atari/',
)


TASKS_PROCGEN = {
    "0-Climber": dict(i=0, eval_i=1, y_range=[0., 1.25], yaxis_dtick=0.25, train_regions=[[5e6 * i, 5e6 * (i + 1)] for i in range(0, 6 * 5, 6)]),
    "1-Dodgeball": dict(i=2, eval_i=3, y_range=[0., 3.], yaxis_dtick=0.5, train_regions=[[5e6 * i, 5e6 * (i + 1)] for i in range(1, 6 * 5, 6)]),
    "2-Ninja": dict(i=4, eval_i=5, y_range=[0., 5.], yaxis_dtick=1.0, train_regions=[[5e6 * i, 5e6 * (i + 1)] for i in range(2, 6 * 5, 6)]),
    "3-Starpilot": dict(i=6, eval_i=7, y_range=[0., 55.], yaxis_dtick=5.0, train_regions=[[5e6 * i, 5e6 * (i + 1)] for i in range(3, 6 * 5, 6)]),
    "4-Bigfish": dict(i=8, eval_i=9, y_range=[0., 18.], yaxis_dtick=3.0, train_regions=[[5e6 * i, 5e6 * (i + 1)] for i in range(4, 6 * 5, 6)]),
    "5-Fruitbot": dict(i=10, eval_i=11, y_range=[-3, 30], yaxis_dtick=5, train_regions=[[5e6 * i, 5e6 * (i + 1)] for i in range(5, 6 * 5, 6)]),
}
MODELS_PROCGEN = {
    "IMPALA": dict(
        name='impala',
        runs=[f'cora/impala_procgen_resblocks/0/run_{i}/impala_procgen_resblocks/0' for i in range(20)],
        color='rgba(77, 102, 133, 1)',
        color_alpha=0.2,
    ),
    "EWC": dict(
        name='ewc',
        runs=[f'cora/ewc_procgen_resblocks/0/run_{i}/ewc_procgen_resblocks/0' for i in [0,1,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21]], # 2, 3 died, replaced with 20,21
        color='rgba(214, 178, 84, 1)',
        color_alpha=0.2,
    ),
    "ONLINE EWC": dict(
        name='online ewc',
        runs=[f'cora/online_ewc_procgen_resblocks/0/run_{i}/online_ewc_procgen_resblocks/0' for i in range(20)],
        color='rgba(106, 166, 110, 1)',
        color_alpha=0.2,
    ),
    "P&C": dict(
        name='pnc',
        runs=[f'cora/pnc_procgen_resblocks/0/run_{i}/pnc_procgen_resblocks/0' for i in range(20)],
        color='rgba(152, 67, 63, 1)',
        color_alpha=0.2,
    ),
    "CLEAR": dict(
        name='clear',
        runs=[f'cora/clear_procgen_resblocks/0/run_{i}/clear_procgen_resblocks/0' for i in [0,1,2,3,4,5,6,7,8,9,10,11,12,13,15,16,17,18,21,22]], #,14, 19 died, replaced with 21, 222
        color='rgba(210, 140, 217, 1)',
        color_alpha=0.2,
    ),
}
PROCGEN = dict(
    models=MODELS_PROCGEN,
    tasks=TASKS_PROCGEN,
    rolling_mean_count=20,
    filter='ma',
    num_cycles=5,
    num_cycles_for_forgetting=1,
    num_task_steps=5e6,
    grid_size=[2, 3],
    which_exp='procgen',
    xaxis_tickvals=list(np.arange(0, 150e6 + 1, 30e6)),
    cache_dir='tmp' #/cache/data_pkls/procgen_resblocks/',
)


TASKS_MINIHACK = {
    "0-Room-Random": dict(i=0, eval_i=1, y_range=[-0.5, 1.], train_regions=[[10e6 * i, 10e6 * (i + 1)] for i in range(0, 15 * 2, 15)]),
    "1-Room-Dark": dict(i=2, eval_i=3, y_range=[-0.5, 1.], train_regions=[[10e6 * i, 10e6 * (i + 1)] for i in range(1, 15 * 2, 15)]),
    "2-Room-Monster": dict(i=4, eval_i=5, y_range=[-0.5, 1.], train_regions=[[10e6 * i, 10e6 * (i + 1)] for i in range(2, 15 * 2, 15)]),
    "3-Room-Trap": dict(i=6, eval_i=7, y_range=[-0.5, 1.], train_regions=[[10e6 * i, 10e6 * (i + 1)] for i in range(3, 15 * 2, 15)]),
    "4-Room-Ultimate": dict(i=8, eval_i=9, y_range=[-0.5, 1.], train_regions=[[10e6 * i, 10e6 * (i + 1)] for i in range(4, 15 * 2, 15)]),
    "5-Corridor-R2": dict(i=10, eval_i=11, y_range=[-1, 1.], train_regions=[[10e6 * i, 10e6 * (i + 1)] for i in range(5, 15 * 2, 15)]),
    "6-Corridor-R3": dict(i=12, eval_i=13, y_range=[-1, 1.], train_regions=[[10e6 * i, 10e6 * (i + 1)] for i in range(6, 15 * 2, 15)]),
    "7-KeyRoom": dict(i=14, eval_i=15, y_range=[-0.5, 1.], train_regions=[[10e6 * i, 10e6 * (i + 1)] for i in range(7, 15 * 2, 15)]),
    "8-KeyRoom-Dark": dict(i=16, eval_i=17, y_range=[-0.5, 1.], train_regions=[[10e6 * i, 10e6 * (i + 1)] for i in range(8, 15 * 2, 15)]),
    "9-River-Narrow": dict(i=18, eval_i=19, y_range=[-0.5, 1.], train_regions=[[10e6 * i, 10e6 * (i + 1)] for i in range(9, 15 * 2, 15)]),
    "10-River-Monster": dict(i=20, eval_i=21, y_range=[-0.5, 1.], train_regions=[[10e6 * i, 10e6 * (i + 1)] for i in range(10, 15 * 2, 15)]),
    "11-River-Lava": dict(i=22, eval_i=23, y_range=[-0.5, 1.], train_regions=[[10e6 * i, 10e6 * (i + 1)] for i in range(11, 15 * 2, 15)]),
    "12-HideNSeek": dict(i=24, eval_i=25, y_range=[-0.5, 1.], train_regions=[[10e6 * i, 10e6 * (i + 1)] for i in range(12, 15 * 2, 15)]),
    "13-HideNSeek-Lava": dict(i=26, eval_i=27, y_range=[-0.5, 1.], train_regions=[[10e6 * i, 10e6 * (i + 1)] for i in range(13, 15 * 2, 15)]),
    "14-CorridorBattle": dict(i=28, eval_i=29, y_range=[-0.5, 1.], train_regions=[[10e6 * i, 10e6 * (i + 1)] for i in range(14, 15 * 2, 15)]),
}

"""TASKS_MINIHACK = {
    "0-RRandom": dict(i=0, eval_i=1, y_range=[-0.5, 1.], train_regions=[[10e6 * i, 10e6 * (i + 1)] for i in range(0, 15 * 2, 15)]),
    "1-RDark": dict(i=2, eval_i=3, y_range=[-0.5, 1.], train_regions=[[10e6 * i, 10e6 * (i + 1)] for i in range(1, 15 * 2, 15)]),
    "2-RMonster": dict(i=4, eval_i=5, y_range=[-0.5, 1.], train_regions=[[10e6 * i, 10e6 * (i + 1)] for i in range(2, 15 * 2, 15)]),
    "3-RTrap": dict(i=6, eval_i=7, y_range=[-0.5, 1.], train_regions=[[10e6 * i, 10e6 * (i + 1)] for i in range(3, 15 * 2, 15)]),
    "4-RUltimate": dict(i=8, eval_i=9, y_range=[-0.5, 1.], train_regions=[[10e6 * i, 10e6 * (i + 1)] for i in range(4, 15 * 2, 15)]),
    "5-CorR2": dict(i=10, eval_i=11, y_range=[-1, 1.], train_regions=[[10e6 * i, 10e6 * (i + 1)] for i in range(5, 15 * 2, 15)]),
    "6-CorR3": dict(i=12, eval_i=13, y_range=[-1, 1.], train_regions=[[10e6 * i, 10e6 * (i + 1)] for i in range(6, 15 * 2, 15)]),
    "7-KeyRoom": dict(i=14, eval_i=15, y_range=[-0.5, 1.], train_regions=[[10e6 * i, 10e6 * (i + 1)] for i in range(7, 15 * 2, 15)]),
    "8-KeyRoom-Dark": dict(i=16, eval_i=17, y_range=[-0.5, 1.], train_regions=[[10e6 * i, 10e6 * (i + 1)] for i in range(8, 15 * 2, 15)]),
    "9-RivNarrow": dict(i=18, eval_i=19, y_range=[-0.5, 1.], train_regions=[[10e6 * i, 10e6 * (i + 1)] for i in range(9, 15 * 2, 15)]),
    "10-RivMonster": dict(i=20, eval_i=21, y_range=[-0.5, 1.], train_regions=[[10e6 * i, 10e6 * (i + 1)] for i in range(10, 15 * 2, 15)]),
    "11-RivLava": dict(i=22, eval_i=23, y_range=[-0.5, 1.], train_regions=[[10e6 * i, 10e6 * (i + 1)] for i in range(11, 15 * 2, 15)]),
    "12-HnS": dict(i=24, eval_i=25, y_range=[-0.5, 1.], train_regions=[[10e6 * i, 10e6 * (i + 1)] for i in range(12, 15 * 2, 15)]),
    "13-HnS-Lava": dict(i=26, eval_i=27, y_range=[-0.5, 1.], train_regions=[[10e6 * i, 10e6 * (i + 1)] for i in range(13, 15 * 2, 15)]),
    "14-CorBattle": dict(i=28, eval_i=29, y_range=[-0.5, 1.], train_regions=[[10e6 * i, 10e6 * (i + 1)] for i in range(14, 15 * 2, 15)]),
}"""

impala_minihack_paths = [f'impala{i}_minihack' for i in range(5)]
impala_minihack_paths.extend([f'vader/cora/impala_minihack_paperdefaults/0/run_{i}/**' for i in range(5)])
clear_minihack_paths = [f'clear{i}_minihack' for i in range(5)]
clear_minihack_paths.extend([f'vader/cora/clear_minihack_paperdefaults_vader/0/run_{i}/**' for i in range(5)])
MODELS_MINIHACK = {
    "IMPALA": dict(
        name='impala',
        runs=impala_minihack_paths,
        # color='rgba(64, 132, 133, 1)',
        color='rgba(77, 102, 133, 1)',
        color_alpha=0.2,
    ),
    "CLEAR": dict(
        name='clear',
        runs=clear_minihack_paths,
        # color='rgba(212, 162, 217, 1)',
        color='rgba(210, 140, 217, 1)',
        color_alpha=0.2,
    ),
}
MINIHACK = dict(
    models=MODELS_MINIHACK,
    tasks=TASKS_MINIHACK,
    rolling_mean_count=20,
    filter='ma',
    num_cycles=2,
    num_cycles_for_forgetting=1,
    num_task_steps=10e6,
    which_exp='minihack',
    xaxis_tickvals=list(np.arange(0, 260e6 + 1, 130e6)),
    metric_eps=0.1,
    cache_dir='tmp/cache/data_pkls/minihack/',
)


TASKS_CHORE_VARY_ENV = {
    "R402": dict(i=0, y_range=[-15, 15.], train_regions=[[1e6 * i, 1e6 * (i + 1)] for i in range(0, 6, 3)]),
    "R419": dict(i=1, y_range=[-15, 15.], train_regions=[[1e6 * i, 1e6 * (i + 1)] for i in range(1, 6, 3)]),
    "R423": dict(i=2, y_range=[-15, 15.], train_regions=[[1e6 * i, 1e6 * (i + 1)] for i in range(2, 6, 3)])
}
MODELS_CHORE_VARY_ENV = {
    "EWC": dict(
        name='ewc',
        runs=[f'vary_envs_2/{i}' for i in [3, 4, 5]],
        color='rgba(214, 178, 84, 1)',
        color_alpha=0.2,
    ),
    "P&C": dict(
        name='pnc',
        runs=[f'vary_envs_2/{i}' for i in [9, 10, 11]],
        color='rgba(152, 67, 63, 1)',
        color_alpha=0.2,
    ),
    "CLEAR": dict(
        name='clear',
        runs=[f'vary_envs_2/{i}' for i in [0, 1, 2]],
        color='rgba(210, 140, 217, 1)',
        color_alpha=0.2,
    ),
}
CHORE_VARY_ENV = dict(
    models=MODELS_CHORE_VARY_ENV,
    tasks=TASKS_CHORE_VARY_ENV,
    rolling_mean_count=5,
    filter='ma',
    num_cycles=2,
    num_cycles_for_forgetting=1,
    num_task_steps=1e6,
    which_exp='chore_vary_env',
    clip_y_range=[-10, 12],
    cache_dir='tmp/cache/data_pkls/chores/',
)


TASKS_CHORE_VARY_TASK = {
    "Hang TP": dict(i=0, y_range=[-15, 15.], train_regions=[[1e6 * i, 1e6 * (i + 1)] for i in range(0, 6, 3)]),
    "Counter": dict(i=1, y_range=[-15, 15.], train_regions=[[1e6 * i, 1e6 * (i + 1)] for i in range(1, 6, 3)]),
    "Cabinet": dict(i=2, y_range=[-15, 15.], train_regions=[[1e6 * i, 1e6 * (i + 1)] for i in range(2, 6, 3)])
}

MODELS_CHORE_VARY_TASK = {
    "EWC": dict(
        name='ewc',
        runs=[f'vary_tasks_2/{i}' for i in [3, 4, 5]],
        color='rgba(214, 178, 84, 1)',
        color_alpha=0.2,
    ),
    "P&C": dict(
        name='pnc',
        runs=[f'vary_tasks_2/{i}' for i in [6, 7, 8]],
        color='rgba(152, 67, 63, 1)',
        color_alpha=0.2,
    ),
    "CLEAR": dict(
        name='clear',
        runs=[f'vary_tasks_2/{i}' for i in [0, 1, 2]],
        color='rgba(210, 140, 217, 1)',
        color_alpha=0.2,
    ),
}
CHORE_VARY_TASK = dict(
    models=MODELS_CHORE_VARY_TASK,
    tasks=TASKS_CHORE_VARY_TASK,
    rolling_mean_count=5,
    filter='ma',
    num_cycles=2,
    num_cycles_for_forgetting=1,
    num_task_steps=1e6,
    which_exp='chore_vary_task',
    clip_y_range=[-10, None],
    cache_dir='tmp/cache/data_pkls/chores/'
)


TASKS_CHORE_VARY_OBJECT = {
    "Fork": dict(i=0, y_range=[-15, 15.], train_regions=[[1e6 * i, 1e6 * (i + 1)] for i in range(0, 6, 3)]),
    "Knife": dict(i=1, y_range=[-15, 15.], train_regions=[[1e6 * i, 1e6 * (i + 1)] for i in range(1, 6, 3)]),
    "Spoon": dict(i=2, y_range=[-15, 15.], train_regions=[[1e6 * i, 1e6 * (i + 1)] for i in range(2, 6, 3)])
}
MODELS_CHORE_VARY_OBJECT = {
    "EWC": dict(
        name='ewc',
        runs=[f'vary_objects_3/{i}' for i in [3, 4, 5]],
        color='rgba(214, 178, 84, 1)',
        color_alpha=0.2,
    ),
    "P&C": dict(
        name='pnc',
        runs=[f'vary_objects_3/{i}' for i in [6, 7, 8]],
        color='rgba(152, 67, 63, 1)',
        color_alpha=0.2,
    ),
    "CLEAR": dict(
        name='clear',
        runs=[f'vary_objects_3/{i}' for i in [0, 1, 2]],
        color='rgba(210, 140, 217, 1)',
        color_alpha=0.2,
    ),
}
CHORE_VARY_OBJECT = dict(
    models=MODELS_CHORE_VARY_OBJECT,
    tasks=TASKS_CHORE_VARY_OBJECT,
    rolling_mean_count=5,
    filter='ma',
    num_cycles=1,
    num_cycles_for_forgetting=1,
    num_task_steps=1e6,
    which_exp='chore_vary_object',
    clip_y_range=[-10, None],
    cache_dir='tmp/cache/data_pkls/chores/'
)


TASKS_CHORE_MULTI_TRAJ = {
    "R19, Cup": dict(i=0, eval_i=1, y_range=[-15, 15.], train_regions=[[1e6 * i, 1e6 * (i + 1)] for i in range(0, 6, 3)]),
    "R13, Potato": dict(i=2, eval_i=3, y_range=[-15, 15.], train_regions=[[1e6 * i, 1e6 * (i + 1)] for i in range(1, 6, 3)]),
    "R02, Lettuce": dict(i=4, eval_i=5, y_range=[-15, 15.], train_regions=[[1e6 * i, 1e6 * (i + 1)] for i in range(2, 6, 3)])
}
MODELS_CHORE_MULTI_TRAJ = {
    "EWC": dict(
        name='ewc',
        runs=[f'multi_traj/{i}' for i in [3, 4, 5]],
        color='rgba(214, 178, 84, 1)',
        color_alpha=0.2,
    ),
    "P&C": dict(
        name='pnc',
        runs=[f'multi_traj/{i}' for i in [6, 7, 8]],
        color='rgba(152, 67, 63, 1)',
        color_alpha=0.2,
    ),
    "CLEAR": dict(
        name='clear',
        runs=[f'multi_traj/{i}' for i in [0, 1, 2]],
        color='rgba(210, 140, 217, 1)',
        color_alpha=0.2,
    ),
}
CHORE_MULTI_TRAJ = dict(
    models=MODELS_CHORE_MULTI_TRAJ,
    tasks=TASKS_CHORE_MULTI_TRAJ,
    rolling_mean_count=5,
    filter='ma',
    num_cycles=1,
    num_cycles_for_forgetting=1,
    num_task_steps=1e6,
    which_exp='chore_multi_traj',
    clip_y_range=[-10, None],
    cache_dir='tmp/cache/data_pkls/chores/'
)


TO_PLOT = dict(
    tag_base='eval_reward',
    cache_dir='tmp/',
    legend_size=30,
    title_size=40,
    axis_size=20,
    axis_label_size=30,
)


def tags_read_event_file(file, tags):
    from tensorflow.python.summary.summary_iterator import summary_iterator

    tags_set = set(tags)

    event_data = collections.defaultdict(list)
    try:
        for event in summary_iterator(file):
            global_step = event.step

            for val in event.summary.value:
                k = val.tag

                if k in tags_set:
                    v = val.simple_value
                    event_data[k].append((global_step, v))
    except Exception as e:
        print(f'truncated: {file}, {e}')

    return event_data


def collate_event_data(event_data_list):
    d = collections.defaultdict(list)
    for x in event_data_list:
        for k, v in x.items():
            d[k].extend(v)

    d_sorted = {}
    for k, v in d.items():
        d_sorted[k] = list(sorted(v, key=lambda x: x[0]))

    return d_sorted


def read_experiment_data(model_v, tags):
    all_run_data = {}

    for run_id in model_v['runs']:
        # check if cached data exists
        cache_filename = f"{TO_PLOT['which_exp']}_{run_id}.pkl".replace(os.path.sep, "-")  # The run may be a path, so de-path-ify it
        cache_p = os.path.join(TO_PLOT['cache_dir'], cache_filename)
        if USE_CACHE and os.path.exists(cache_p):
            print(f'loading cached: {cache_p}')
            event_data = pickle.load(open(cache_p, 'rb'))
        else:
            # iterate thru event files
            d = []
            pattern = os.path.join(TO_PLOT['exp_dir'], f'{run_id}', 'events.out.tfevents.*')  # TODO: not general to Eliot's setup?
            for file in sorted(glob(pattern, recursive=True)):
                print(f'reading event file: {file}')
                event_data = tags_read_event_file(file, tags)
                d.append(event_data)

            if len(d) == 0:
                raise RuntimeError(f'no event files found: {pattern}')

            event_data = collate_event_data(d)

            if SAVE_IN_CACHE:
                pickle.dump(event_data, open(cache_p, 'wb'))

        all_run_data[run_id] = event_data
    return all_run_data


def one_sided_ema(xolds, yolds, low=None, high=None, n=512, decay_steps=1., low_counts_threshold=1e-8):
    '''
    perform one-sided (causal) EMA (exponential moving average)
    smoothing and resampling to an even grid with n points.
    Does not do extrapolation, so we assume
    xolds[0] <= low && high <= xolds[-1]
    Arguments:
    xolds: array or list  - x values of data. Needs to be sorted in ascending order
    yolds: array of list  - y values of data. Has to have the same length as xolds
    low: float            - min value of the new x grid. By default equals to xolds[0]
    high: float           - max value of the new x grid. By default equals to xolds[-1]
    n: int                - number of points in new x grid
    decay_steps: float    - EMA decay factor, expressed in new x grid steps.
    low_counts_threshold: float or int
                          - y values with counts less than this value will be set to NaN
    Returns:
        tuple sum_ys, count_ys where
            xs        - array with new x grid
            ys        - array of EMA of y at each point of the new x grid
            count_ys  - array of EMA of y counts at each point of the new x grid
    '''

    low = xolds[0] if low is None else low
    high = xolds[-1] if high is None else high

    assert xolds[0] <= low, 'low = {} < xolds[0] = {} - extrapolation not permitted!'.format(low, xolds[0])
    assert xolds[-1] >= high, 'high = {} > xolds[-1] = {}  - extrapolation not permitted!'.format(high, xolds[-1])
    assert len(xolds) == len(yolds), 'length of xolds ({}) and yolds ({}) do not match!'.format(len(xolds), len(yolds))

    xolds = xolds.astype('float64')
    yolds = yolds.astype('float64')

    luoi = 0 # last unused old index
    sum_y = 0.
    count_y = 0.
    xnews = np.linspace(low, high, n)
    decay_period = (high - low) / (n - 1) * decay_steps
    interstep_decay = np.exp(- 1. / decay_steps)
    sum_ys = np.zeros_like(xnews)
    count_ys = np.zeros_like(xnews)
    for i in range(n):
        xnew = xnews[i]
        sum_y *= interstep_decay
        count_y *= interstep_decay
        while True:
            if luoi >= len(xolds):
                break
            xold = xolds[luoi]
            if xold <= xnew:
                decay = np.exp(- (xnew - xold) / decay_period)
                sum_y += decay * yolds[luoi]
                count_y += decay
                luoi += 1
            else:
                break
        sum_ys[i] = sum_y
        count_ys[i] = count_y

    ys = sum_ys / count_ys
    ys[count_ys < low_counts_threshold] = np.nan

    return xnews, ys, count_ys


def smooth(y, radius, mode='two_sided', valid_only=False):
    '''
    Smooth signal y, where radius is determines the size of the window
    mode='twosided':
        average over the window [max(index - radius, 0), min(index + radius, len(y)-1)]
    mode='causal':
        average over the window [max(index - radius, 0), index]
    valid_only: put nan in entries where the full-sized window is not available
    '''
    assert mode in ('two_sided', 'causal')
    if len(y) < 2*radius+1:
        return np.ones_like(y) * y.mean()
    elif mode == 'two_sided':
        convkernel = np.ones(2 * radius+1)
        out = np.convolve(y, convkernel,mode='same') / np.convolve(np.ones_like(y), convkernel, mode='same')
        if valid_only:
            out[:radius] = out[-radius:] = np.nan
    elif mode == 'causal':
        convkernel = np.ones(radius)
        out = np.convolve(y, convkernel,mode='full') / np.convolve(np.ones_like(y), convkernel, mode='full')
        out = out[:-radius+1]
        if valid_only:
            out[:radius] = np.nan
    return out


def post_processing(data, tags):
    post_processed_data = {}
    for run_id, d in data.items():
        new_d = {}
        for k in tags:
            if k not in d:
                continue

            run = d[k]

            xs = np.array([run_datum[0] for run_datum in run])
            ys = [run_datum[1] for run_datum in run]

            if TO_PLOT.get("clip_y_range", None) is not None:
                clip_range = TO_PLOT["clip_y_range"]
                ys = np.array(ys).clip(min=clip_range[0], max=clip_range[1])

            if TO_PLOT['filter'] == 'ma':
                rolling_accumulator = collections.deque(maxlen=TO_PLOT['rolling_mean_count'])
                for x_id, x in enumerate(xs):
                    rolling_accumulator.append(ys[x_id])
                    ys[x_id] = np.array(rolling_accumulator).mean()
            elif TO_PLOT['filter'] == 'ema':
                xs, ys, _ = one_sided_ema(np.array(xs), np.array(ys), n=50)
            elif TO_PLOT['filter'] == 'smooth':
                ys = smooth(ys, TO_PLOT['rolling_mean_count'], mode='causal')
            else:
                raise ValueError

            processed_run = list(zip(xs, ys))

            new_d[k] = processed_run

        post_processed_data[run_id] = new_d
    return post_processed_data


def combine_experiment_data(data, tags):
    num_runs = len(data.keys())

    d = {}
    for k in tags:
        xs = []
        ys = []
        for run_id in data.keys():
            run_data = data[run_id][k]

            xs.append(np.array([data_point[0] for data_point in run_data]))
            ys.append(np.array([data_point[1] for data_point in run_data]))

        # Get the bounds and the number of samples to take for the interpolation we're about to do
        # We don't try interpolate out of the bounds of what was collected (i.e. below an experiment's min, or above its max)
        min_x = np.array([x.min() for x in xs]).max()
        max_x = np.array(
            [x.max() for x in xs]
        ).min()  # Get the min of the maxes so we're not interpolating past the end of collected data
        num_points = (
            np.array([len(x) for x in xs]).max() * 2
        )  # Doubled from my vague signal processing recollection to capture the underlying signal (...very rough)

        # Get the regular interval we'll be interpolating to
        interpolated_xs = np.linspace(min_x, max_x, num_points)
        interpolated_ys_per_run = []

        # Interpolate each run
        for run_id, run_ys in enumerate(ys):
            run_xs = xs[run_id]
            interpolated_ys = np.interp(interpolated_xs, run_xs, run_ys)
            interpolated_ys_per_run.append(interpolated_ys)

        y_series = np.array(interpolated_ys_per_run)
        y_means = y_series.mean(0)
        y_stds = sem(y_series)  # Computing the standard error of the mean, since that's what we're actually interested in here.

        d[k] = (interpolated_xs, y_means, y_stds)

    return d


def create_scatters(data, model_k, model_v, dash=False, mean_showlegend=True, alpha=None):
    x, y_mean, y_std = data

    y_lower = y_mean - y_std
    y_upper = y_mean + y_std

    line_color = copy.deepcopy(model_v['color'])
    fill_color = copy.deepcopy(line_color)
    fill_color = fill_color.replace(', 1)', f", {model_v['color_alpha']})")

    if alpha is not None:
       line_color = line_color.replace(', 1)', f", {alpha})")

    upper_bound = go.Scatter(
        x=x,
        y=y_upper,
        mode='lines',
        line=dict(width=0),
        fillcolor=fill_color,
        fill='tonexty',
        name=model_k,
        showlegend=False,
    )

    line = dict(color=line_color, width=3)
    if dash:
        line['dash'] = dash

    trace = go.Scatter(
        x=x,
        y=y_mean,
        mode='lines',
        line=line,
        fillcolor=fill_color,
        fill='tonexty',
        name=model_k,
        showlegend=mean_showlegend,
    )

    lower_bound = go.Scatter(
        x=x, y=y_lower, line=dict(width=0), mode='lines', name=model_k, showlegend=False
    )

    # Trace order can be important
    # with continuous error bars
    traces = [lower_bound, trace, upper_bound]

    return traces


def plot_models(d):
    num_task_steps = TO_PLOT['num_task_steps']
    num_cycles = TO_PLOT['num_cycles']
    num_tasks = TO_PLOT.get('num_tasks', len(TO_PLOT['tasks']))
    x_range = [-10, num_task_steps * num_tasks * num_cycles]

    axis_size = TO_PLOT['axis_size']
    axis_label_size = TO_PLOT['axis_label_size']
    legend_size = TO_PLOT['legend_size']
    title_size = TO_PLOT['title_size']
    which_exp = TO_PLOT['which_exp']

    figures = {}

    for task_i, (task_k, task_v) in enumerate(TO_PLOT['tasks'].items()):
        fig = go.Figure()

        # min_x = 0  # Effectively defaulting to 0
        # max_x = 0

        y_range = task_v.get('y_range', None)
        train_regions = task_v.get('train_regions', None)
        showlegend = True
        yaxis_dtick = task_v.get('yaxis_dtick', None)

        tag = f"{TO_PLOT['tag_base']}/{task_v['i']}"
        if 'eval_i' in task_v.keys():
            eval_tag = f"{TO_PLOT['tag_base']}/{task_v['eval_i']}"
        else:
            eval_tag = None

        for model_k, model_v in TO_PLOT['models'].items():
            data = d[model_k][tag]

            _kwargs = {}
            if eval_tag is not None:
                _kwargs = dict(alpha=0.5, dash='dash', mean_showlegend=False)

            low_trace, trace, up_trace = create_scatters(data, model_k, model_v, **_kwargs)

            fig.add_trace(low_trace)
            fig.add_trace(trace)
            fig.add_trace(up_trace)

        if eval_tag is not None:
            for model_k, model_v in TO_PLOT['models'].items():
                data = d[model_k][eval_tag]

                low_trace, trace, up_trace = create_scatters(data, model_k, model_v)

                fig.add_trace(low_trace)
                fig.add_trace(trace)
                fig.add_trace(up_trace)

        yaxis_range = [y_range[0], y_range[1] * 1.01]

        yaxis_label = TO_PLOT.get("yaxis_label", "Expected Return")
        fig.update_layout(
            yaxis=dict(
                title=dict(text=yaxis_label, font=dict(size=axis_label_size)),
                range=yaxis_range,
                tick0=0,
                dtick=yaxis_dtick,
                tickfont=dict(size=axis_size),
                gridcolor='rgb(230,236,245)',
            ),
            xaxis=dict(
                title=dict(text='Step', font=dict(size=axis_label_size)),
                range=x_range,
                tickvals=TO_PLOT.get('xaxis_tickvals', None),
                tickfont=dict(size=axis_size),
            ),
            title=dict(text=f'\n{task_k}', font=dict(size=title_size)),
            legend=dict(font=dict(size=legend_size, color="black"), x=1.15),
            showlegend=showlegend,
            title_x=0.15,
            plot_bgcolor='rgb(255,255,255)',
        )

        if train_regions is not None:
            for shaded_region in train_regions:
                fig.add_shape(
                    # Rectangle reference to the axes
                    type="rect",
                    xref="x",
                    yref="y",
                    x0=shaded_region[0],
                    y0=y_range[0],
                    x1=shaded_region[1],
                    y1=y_range[1],
                    line=dict(
                        color="rgba(150, 150, 180, .3)",
                        width=1,
                    ),
                    fillcolor="rgba(230, 236, 245, 0.3)"
                )

        fig.write_image(f'{which_exp}_{task_i}.pdf')
        figures[task_i] = fig
        fig.show()

    return figures


def get_rewards_for_region(xs, ys, region):
        valid_x_mask_lower = xs > region[0] if region[0] is not None else True  # If we have no lower bound specified, all xs are valid
        valid_x_mask_upper = xs < region[1] if region[1] is not None else True
        valid_x_mask = valid_x_mask_lower * valid_x_mask_upper

        return ys[valid_x_mask]


def compute_forgetting_metric(task_results, task_steps, task_id, num_tasks, num_cycles, return_scale):
    """
    We compute how much is forgotten of task (task_id) as each subsequent (subsequent_task_id) is learned.
    """
    per_run_forgetting_per_subsequent = {id: {} for id in range(num_tasks)}  # Inner dict maps cycle to total

    for run_id, task_result in enumerate(task_results):
        xs = np.array([t[0] for t in task_result])
        ys = np.array([t[1] for t in task_result]) * return_scale

        # Select only the rewards from the region up to and including the training of the given task
        task_rewards = get_rewards_for_region(xs, ys, [None, (task_id+1) * task_steps])
        max_task_value = task_rewards.max()

        for cycle_id in range(num_cycles):
            for subsequent_task_id in range(num_tasks):
                # It's not really "catastrophic forgetting" if we haven't seen the task yet, so skip the early tasks
                if cycle_id == 0 and subsequent_task_id <= task_id:
                    continue

                offset = cycle_id * num_tasks

                if USE_ISOLATED_FORGETTING:
                    task_rewards = get_rewards_for_region(xs, ys, [None, (subsequent_task_id + offset) * task_steps])
                    max_task_value = task_rewards[-1]

                subsequent_region = [(subsequent_task_id + offset) * task_steps,
                                     (subsequent_task_id + offset + 1) * task_steps]
                subsequent_task_rewards = get_rewards_for_region(xs, ys, subsequent_region)
                last_reward = subsequent_task_rewards[-1]
                forgetting = max_task_value - last_reward

                if cycle_id not in per_run_forgetting_per_subsequent[subsequent_task_id]:
                    per_run_forgetting_per_subsequent[subsequent_task_id][cycle_id] = []
                per_run_forgetting_per_subsequent[subsequent_task_id][cycle_id].append(forgetting)

    # We'll do this during augmenting the table, so we have the raw data for column/row/full table computations
    """average_forgetting = {}
    standard_error = {}
    for subsequent_id, subsequent_metrics in per_run_forgetting_per_subsequent.items():
        average_forgetting[subsequent_id] = {}
        standard_error[subsequent_id] = {}
        for cycle_id in subsequent_metrics.keys():
            average_forgetting[subsequent_id][cycle_id] = sum(per_run_forgetting_per_subsequent[subsequent_id][cycle_id]) / len(task_results)
            standard_error[subsequent_id][cycle_id] = sem(per_run_forgetting_per_subsequent[subsequent_id][cycle_id])"""

    #return average_forgetting, standard_error
    return per_run_forgetting_per_subsequent


def compute_forward_transfer_metric(task_results, task_steps, prior_task_ids, return_scale):
    """
    We compute how much is learned of task (task_id) by each previous task, before task (task_id) is learned at all.
    """
    per_run_transfer_per_prior = {id: [] for id in prior_task_ids}  # The id maps to task_id, and the entries of the array correspond to separate runs

    for run_id, task_result in enumerate(task_results):
        xs = np.array([t[0] for t in task_result])
        ys = np.array([t[1] for t in task_result]) * return_scale

        # Select only the rewards from the region up to and including the training of the given task
        initial_task_value = ys[0]  # TODO: this isn't necessarily a robust average

        for prior_task_id in prior_task_ids:
            prior_region = [prior_task_id * task_steps, (prior_task_id+1) * task_steps]  # TODO: could do from the end of the task up to the subsequent one we're looking at...
            subsequent_task_rewards = get_rewards_for_region(xs, ys, prior_region)
            last_reward = subsequent_task_rewards[-1]
            baseline = initial_task_value

            if USE_ISOLATED_ZSFT and prior_task_id > 0:
                pre_task_region = [0, prior_task_id * task_steps]  # Get the rewards up to and not including our "previous task"
                subsequent_pre_task_rewards = get_rewards_for_region(xs, ys, pre_task_region)
                baseline = subsequent_pre_task_rewards[-1]

            transfer = last_reward - baseline
            per_run_transfer_per_prior[prior_task_id].append(transfer)

    """average_transfer = {}
    standard_error = {}
    for prior_id in per_run_transfer_per_prior.keys():
        average_transfer[prior_id] = sum(per_run_transfer_per_prior[prior_id]) / len(task_results)
        standard_error[prior_id] = sem(per_run_transfer_per_prior[prior_id])

    return average_transfer, standard_error"""
    return per_run_transfer_per_prior


def get_metric_tags():
    """
    Get the tags to be used during computation of metrics. It is assumed that the order is consistent: i.e. tags
    A, B, C, D will be used to compute how much forgetting D causes for B and C.
    :return:
    """
    task_ids = [task["eval_i"] if "eval_i" in task else task["i"] for task in TO_PLOT["tasks"].values()]
    tags = [f"{TO_PLOT['tag_base']}/{id}" for id in task_ids]
    return tags


def compute_metrics(data):
    # Grab the tag ids we will use to evaluate the metrics: if we collected explicit eval data, use that.
    tags = get_metric_tags()
    num_tasks = len(tags)
    metrics = {}

    # For each task (labeled by a tag), grab all of the associated runs, then compute the metrics on them
    for task_id, task_tag in enumerate(tags):
        per_task_data = []
        for run_data in data.values():
            per_task_data.append(run_data[task_tag])

        # Scale by the largest (absolute) return seen for this task  # TODO: should only be first cycle
        max_return = np.abs(np.concatenate([np.array([run[1] for run in task]) for task in per_task_data])).max()

        # Compute the amount this task was forgotten by subsequent tasks
        # Forgetting will map task to a dictionary (cycle_id: amount of forgetting)
        per_run_forgetting = compute_forgetting_metric(per_task_data, TO_PLOT["num_task_steps"], task_id, num_tasks,
                                               num_cycles=TO_PLOT["num_cycles_for_forgetting"], return_scale=1/max_return)

        prior_task_ids = list(range(len(tags)))[:task_id]
        per_run_transfer = compute_forward_transfer_metric(per_task_data, TO_PLOT["num_task_steps"], prior_task_ids,
                                                   return_scale=1/max_return)

        metrics[task_tag] = {"forgetting": per_run_forgetting, "transfer": per_run_transfer}

    return metrics


def truncate_task_names(task_names, max_len):
    new_task_names = []
    for task_name in task_names:
        if len(task_name) > max_len:
            new_task_name = task_name[:max_len] + ".."
        else:
            new_task_name = task_name

        new_task_names.append(new_task_name)

    return new_task_names


def generate_metric_table(metric_table, metric_error_table, negative_as_green, table_caption, num_cycles, metric_scale, max_task_name_len=7):
    def style_forgetting_table(v):
        default_mixin_val = 40

        # Mixin => how much of the color (vs how much white)
        v = "--" if v == "--" else float(v.split("±")[0])  # Undo the SEM inclusion. A bit hacky but whatever
        mixin_val = 0 if v == '--' else int(np.abs(v) * default_mixin_val/metric_scale)
        if v == '--':
            color = "green"  # Doesn't matter
        elif (not negative_as_green and v > 0) or (negative_as_green and v < 0):
            color = "green"
        else:
            color = "red"

        return f"cellcolor:{{{color}!{mixin_val}}}"  # Exclamation point is a mixin - says how much of the given color to use (mixed in with white)

    tasks = truncate_task_names(list(TO_PLOT["tasks"].keys()), max_len=20) #max_task_name_len)

    if num_cycles == 1:
        col_names = [f"{tasks[x]}" for c in range(num_cycles) for x in range(len(tasks))]
    else:
        col_names = [f"{tasks[x]} (C{c})" for c in range(num_cycles) for x in range(len(tasks))]
    col_names += ["Avg ± SEM"]
    row_names = [f"{tasks[x]}" for x in range(len(tasks))] + ["Avg ± SEM"]

    # Convert to string and include the error metric
    string_metric_table = np.array(metric_table, dtype=object)
    for i in range(len(metric_table)):
        for j in range(len(metric_table[0])):
            if not np.isnan(metric_table[i][j]):
                string_metric_table[i][j] = f"{metric_table[i][j]:.1f} ± {metric_error_table[i][j]:.1f}"
            else:
                string_metric_table[i][j] = "--"

    # Styling for Latex isn't quite the same as other formats, see: https://pandas.pydata.org/docs/reference/api/pandas.io.formats.style.Styler.to_latex.html
    data_frame = pd.DataFrame(string_metric_table)
    data_frame = data_frame.rename(columns=lambda x: col_names[x])  # Name the columns: "Task Name (C cycle_id)"
    data_frame = data_frame.rename(index=lambda x: row_names[x])  # Name the rows: "Task Name"

    #data_style = data_frame.style.format(precision=1, na_rep="--")
    data_style = data_frame.style.applymap(style_forgetting_table)
    data_style = data_style.set_table_styles([
        {'selector': 'toprule', 'props': ':hline;'},
        {'selector': 'bottomrule', 'props': ':hline;'},
    ], overwrite=False)

    # Column styles should be |l|llll|l| The first isolates the row names, the last the row-wise means
    column_style = ''.join(['l' for _ in range(len(data_style.columns) - 1)])
    latex_metrics = data_style.to_latex(column_format=f"|l|{column_style}|l|")  # Requires pandas > 1.3.0 (conda install pandas==1.3.0)

    # TODO: not putting the hline under the column names because I'm not sure how at the moment, so doing that manually

    return f"\subfloat[{table_caption}]{{ \n {latex_metrics}}}"


def augment_with_consolidated_statistics(metric_table, metric_error_table, model_metrics, average_over_cycles=False):
    # TODO: unused function

    num_cycles = TO_PLOT["num_cycles_for_forgetting"] #1  # TODO: this is because no metrics are aggregating over cycles anymore... # TO_PLOT["num_cycles"]
    num_tasks = len(TO_PLOT["tasks"])
    metric_table = np.array(metric_table, dtype=np.float)
    metric_error_table = np.array(metric_error_table, dtype=np.float)
    all_mean = np.nanmean(metric_table)  # Compute first, so it's before any averaging across dimensions

    if average_over_cycles:
        # Split the data into the sets of cycles, then average over
        cycle_splits = []
        for i in range(0, len(metric_table[0]), num_tasks):
            cycle_data = metric_table[:, i:i+num_tasks]
            cycle_splits.append(cycle_data)
        metric_table = np.nanmean(np.array(cycle_splits), axis=0)

    # Truncating the table *before* computing the metrics.
    metric_table = metric_table[:, :num_tasks*num_cycles]
    row_wise_mean = np.nanmean(metric_table, axis=1)
    column_wise_mean = np.nanmean(metric_table, axis=0)

    # Compute the row-wise statistics. We do this by
    # The task_data contains per-run_data. The reason for this is that the metrics for *within* a run are not independent, so we can't compute SEM naively
    # treating them as though they were independent. So what we do is we average across the appropriate dimension

    # Put all_mean at the end of column_wise because we append it second, so it'll end up in the corner
    column_wise_mean = np.concatenate((column_wise_mean, np.array([all_mean])))

    # Concatenate our consolidated stats onto the main table for table construction
    metric_table = np.concatenate((metric_table, np.expand_dims(row_wise_mean, 1)), axis=1)
    metric_table = np.concatenate((metric_table, np.expand_dims(column_wise_mean, 0)), axis=0)

    return metric_table, metric_error_table, all_mean


def plot_metrics(metrics):
    tags = get_metric_tags()
    num_tasks = len(tags)
    num_cycles = TO_PLOT["num_cycles_for_forgetting"]  # TODO: const, it's used a few places. TO_PLOT["num_cycles"]
    metric_scale = 10  # Consistent across tasks, since they have all been normalized

    for model_name, model_metrics in metrics.items():
        # Pre-allocate our tables
        forgetting_table = [[None for _ in range(num_tasks * num_cycles + 1)] for _ in range(num_tasks + 1)]
        transfer_table = [[None for _ in range(num_tasks + 1)] for _ in range(num_tasks + 1)]  # Zero-shot transfer, so we don't plot all the cycles

        forgetting_error_table = [[None for _ in range(num_tasks * num_cycles + 1)] for _ in range(num_tasks + 1)]
        transfer_error_table = [[None for _ in range(num_tasks + 1)] for _ in range(num_tasks + 1)]  # Zero-shot transfer, so we don't plot all the cycles

        # To ensure our standard error of the mean statistics are using independent data, we average the metrics over the run across the appropriate axis
        task_id_run_aggregates_forgetting = {}  # For a given task id, aggregate the run id data (across impactor)
        impactor_id_run_aggregates_forgetting = {}  # For a given impactor id, aggregate the run id data (across task)

        task_id_run_aggregates_transfer = {}  # For a given task id, aggregate the run id data (across impactor)
        impactor_id_run_aggregates_transfer = {}  # For a given impactor id, aggregate the run id data (across task)

        for task_id, tag in enumerate(tags):
            task_data = model_metrics[tag]

            # Fill in forgetting data. "Impactor" means the task that is causing the change in the current task (subsequent task for forgetting)
            forgetting_data = task_data["forgetting"]

            for impactor_id in range(num_tasks):
                impact_data = forgetting_data.get(impactor_id, {})

                for cycle_id in range(num_cycles):
                    impact_cycle_run_data = impact_data.get(cycle_id, None)

                    impact_cycle_data = sum(impact_cycle_run_data) / len(impact_cycle_run_data) if impact_cycle_run_data is not None else None
                    impact_cycle_error = sem(impact_cycle_run_data) if impact_cycle_run_data is not None else None

                    forgetting_table[task_id][cycle_id * num_tasks + impactor_id] = impact_cycle_data * metric_scale if impact_cycle_data is not None else None
                    forgetting_error_table[task_id][cycle_id * num_tasks + impactor_id] = impact_cycle_error * metric_scale if impact_cycle_error is not None else None

                    # Aggregate statistics holding the task_id and impactor_id constant:
                    # First we average the data over the same run, to give us a per-run forgetting statistic
                    if impact_cycle_run_data is not None:
                        for run_id in range(len(impact_cycle_run_data)):
                            # Aggregate by task_id
                            if task_id not in task_id_run_aggregates_forgetting:
                                task_id_run_aggregates_forgetting[task_id] = {}

                            if run_id not in task_id_run_aggregates_forgetting[task_id]:
                                task_id_run_aggregates_forgetting[task_id][run_id] = []

                            task_id_run_aggregates_forgetting[task_id][run_id].append(impact_cycle_run_data[run_id])

                            # Aggregate by impactor
                            if impactor_id not in impactor_id_run_aggregates_forgetting:
                                impactor_id_run_aggregates_forgetting[impactor_id] = {}

                            if run_id not in impactor_id_run_aggregates_forgetting[impactor_id]:
                                impactor_id_run_aggregates_forgetting[impactor_id][run_id] = []

                            impactor_id_run_aggregates_forgetting[impactor_id][run_id].append(impact_cycle_run_data[run_id])

            # Fill in the transfer data
            transfer_data = task_data["transfer"]
            for impactor_id in range(num_tasks):
                impact_cycle_run_data = transfer_data.get(impactor_id, None)

                impact_data = sum(impact_cycle_run_data) / len(impact_cycle_run_data) if impact_cycle_run_data is not None else None
                impact_error = sem(impact_cycle_run_data) if impact_cycle_run_data is not None else None

                transfer_table[task_id][impactor_id] = impact_data * metric_scale if impact_data is not None else None
                transfer_error_table[task_id][impactor_id] = impact_error * metric_scale if impact_data is not None else None

                # Aggregate statistics holding the task_id and impactor_id constant:
                # First we average the data over the same run, to give us a per-run forgetting statistic
                if impact_cycle_run_data is not None:
                    for run_id in range(len(impact_cycle_run_data)):
                        # Aggregate by task_id
                        if task_id not in task_id_run_aggregates_transfer:
                            task_id_run_aggregates_transfer[task_id] = {}

                        if run_id not in task_id_run_aggregates_transfer[task_id]:
                            task_id_run_aggregates_transfer[task_id][run_id] = []

                        task_id_run_aggregates_transfer[task_id][run_id].append(impact_cycle_run_data[run_id])

                        # Aggregate by impactor
                        if impactor_id not in impactor_id_run_aggregates_transfer:
                            impactor_id_run_aggregates_transfer[impactor_id] = {}

                        if run_id not in impactor_id_run_aggregates_transfer[impactor_id]:
                            impactor_id_run_aggregates_transfer[impactor_id][run_id] = []

                        impactor_id_run_aggregates_transfer[impactor_id][run_id].append(impact_cycle_run_data[run_id])

        # Generate consolidated statistics
        for task_id in range(len(forgetting_table)):
            if task_id in task_id_run_aggregates_forgetting:
                task_id_forgetting = np.array(list(task_id_run_aggregates_forgetting[task_id].values())).mean(axis=1)
                forgetting_table[task_id][-1] = metric_scale * task_id_forgetting.mean(axis=0)  # Along the axes for consistency with sem
                forgetting_error_table[task_id][-1] = metric_scale * sem(task_id_forgetting)

            if task_id in task_id_run_aggregates_transfer:
                task_id_transfer = np.array(list(task_id_run_aggregates_transfer[task_id].values())).mean(axis=1)
                transfer_table[task_id][-1] = metric_scale * task_id_transfer.mean(axis=0)
                transfer_error_table[task_id][-1] = metric_scale * sem(task_id_transfer)

            for impactor_id in range(len(forgetting_table[0])):
                if impactor_id in impactor_id_run_aggregates_forgetting:
                    impactor_id_forgetting = np.array(list(impactor_id_run_aggregates_forgetting[impactor_id].values())).mean(axis=1)
                    forgetting_table[-1][impactor_id] = metric_scale * impactor_id_forgetting.mean(axis=0)
                    forgetting_error_table[-1][impactor_id] = metric_scale * sem(impactor_id_forgetting)

                if impactor_id in impactor_id_run_aggregates_transfer:
                    impactor_id_transfer = np.array(list(impactor_id_run_aggregates_transfer[impactor_id].values())).mean(axis=1)
                    transfer_table[-1][impactor_id] = metric_scale * impactor_id_transfer.mean(axis=0)
                    transfer_error_table[-1][impactor_id] = metric_scale * sem(impactor_id_transfer)

        forgetting_table = np.array(forgetting_table, dtype=np.float)
        forgetting_error_table = np.array(forgetting_error_table, dtype=np.float)

        transfer_table = np.array(transfer_table, dtype=np.float)
        transfer_error_table = np.array(transfer_error_table, dtype=np.float)

        # Complete the corners by aggregating all data from each run
        # Forgetting corner
        all_task_id_run_data_forgetting = {}
        for task_id in task_id_run_aggregates_forgetting.keys():
            for run_id in task_id_run_aggregates_forgetting[task_id].keys():
                if run_id not in all_task_id_run_data_forgetting:
                    all_task_id_run_data_forgetting[run_id] = []

                all_task_id_run_data_forgetting[run_id].extend(task_id_run_aggregates_forgetting[task_id][run_id])

        all_task_id_run_agg_forgetting = np.array(list(all_task_id_run_data_forgetting.values())).mean(axis=1)
        forgetting_table[-1][-1] = metric_scale * all_task_id_run_agg_forgetting.mean()
        forgetting_error_table[-1][-1] = metric_scale * sem(all_task_id_run_agg_forgetting)

        # Transfer corner
        all_task_id_run_data_transfer = {}
        for task_id in task_id_run_aggregates_transfer.keys():
            for run_id in task_id_run_aggregates_transfer[task_id].keys():
                if run_id not in all_task_id_run_data_transfer:
                    all_task_id_run_data_transfer[run_id] = []

                all_task_id_run_data_transfer[run_id].extend(task_id_run_aggregates_transfer[task_id][run_id])

        all_task_id_run_agg_transfer = np.array(list(all_task_id_run_data_transfer.values())).mean(axis=1)
        transfer_table[-1][-1] = metric_scale * all_task_id_run_agg_transfer.mean()
        transfer_error_table[-1][-1] = metric_scale * sem(all_task_id_run_agg_transfer)

        #average_forgetting_over_cycles = True
        #forgetting_table, forgetting_error_table, forgetting_mean = augment_with_consolidated_statistics(forgetting_table, forgetting_error_table, model_metrics, average_over_cycles=average_forgetting_over_cycles)
        #transfer_table, transfer_error_table, transfer_mean = augment_with_consolidated_statistics(transfer_table, transfer_error_table, model_metrics)

        latex_forgetting_metrics = generate_metric_table(forgetting_table, forgetting_error_table, negative_as_green=True,
                                                         table_caption=f"{model_name}",
                                                         num_cycles=TO_PLOT["num_cycles_for_forgetting"], # if average_forgetting_over_cycles else TO_PLOT["num_cycles_for_forgetting"],
                                                         metric_scale=metric_scale)
        latex_transfer_metrics = generate_metric_table(transfer_table, transfer_error_table, negative_as_green=False,
                                                       table_caption=f"{model_name}",
                                                       num_cycles=1,
                                                       metric_scale=metric_scale)
        #print(f"{model_name} forgetting mean: {forgetting_mean}")
        #print(f"{model_name} forgetting latex: \n\n{latex_forgetting_metrics}\n\n")
        print(f"\n\n{latex_forgetting_metrics}\n\n")

        #print(f"{model_name} transfer mean: {transfer_mean}")
        #print(f"{model_name} transfer latex: \n\n{latex_transfer_metrics}\n\n")
        #print(f"\n\n{latex_transfer_metrics}\n\n")


def visualize(plot_spec=None):
    if plot_spec is not None:
        TO_PLOT.update(plot_spec)

    tags = []
    for task_k, task_v in TO_PLOT['tasks'].items():
        tags.append(f"{TO_PLOT['tag_base']}/{task_v['i']}")
        if 'eval_i' in task_v.keys():
            tags.append(f"{TO_PLOT['tag_base']}/{task_v['eval_i']}")
    print(f'tags: {tags}')

    d = {}
    all_metrics = {}
    for model_k, model_v in TO_PLOT['models'].items():
        print(f'loading data for model: {model_k}')
        data = read_experiment_data(model_v, tags)
        data = post_processing(data, tags)

        # Compute the metrics after we've smoothed (so our values are more representative) but before we interpolate
        # to combine the runs together
        metrics = compute_metrics(data)
        all_metrics[model_k] = metrics

        data = combine_experiment_data(data, tags)
        d[model_k] = data

        for task_key, task_data in data.items():
            max_timesteps = TO_PLOT["num_cycles"] * len(data) * TO_PLOT["num_task_steps"]
            final_index = np.where(task_data[0] < max_timesteps)[0][-1]
            print(f"{model_k}: task {task_key}: final performance: {task_data[1][final_index]:.2f} \pm {task_data[2][final_index]:.2f}")

    plot_models(d)
    #plot_metrics(all_metrics)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', type=str, help='experiment dir')
    args = parser.parse_args()
    TO_PLOT['exp_dir'] = args.d

    #exp_data = ATARI
    exp_data = PROCGEN
    #exp_data = MINIHACK
    #exp_data = CHORE_VARY_ENV
    #exp_data = CHORE_VARY_TASK
    #exp_data = CHORE_VARY_OBJECT
    #exp_data = CHORE_MULTI_TRAJ
    TO_PLOT.update(**exp_data)

    visualize()
