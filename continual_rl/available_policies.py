

class PolicyStruct(object):
    def __init__(self, policy, config):
        self.policy = policy
        self.config = config


class LazyDict(dict):
    """
    Takes a dictionary of lambdas, and executes the lambda on get for the item.
    The purpose of of this is to be able to load dependencies only as we need them, so users don't have to install
    things they'll never need.
    """
    def __init__(self, dict):
        super().__init__(dict)
        self._dict = dict

    def __getitem__(self, item):
        return self._dict[item]()


def load_discrete_random():
    from continual_rl.policies.discrete_random.discrete_random_policy import DiscreteRandomPolicy
    from continual_rl.policies.discrete_random.discrete_random_policy_config import DiscreteRandomPolicyConfig
    return PolicyStruct(DiscreteRandomPolicy, DiscreteRandomPolicyConfig)


def load_ppo():
    from continual_rl.policies.ppo.ppo_policy import PPOPolicy
    from continual_rl.policies.ppo.ppo_policy_config import PPOPolicyConfig
    return PolicyStruct(PPOPolicy, PPOPolicyConfig)


def load_impala():
    from continual_rl.policies.impala.impala_policy import ImpalaPolicy
    from continual_rl.policies.impala.impala_policy_config import ImpalaPolicyConfig
    return PolicyStruct(ImpalaPolicy, ImpalaPolicyConfig)


def load_clear():
    from continual_rl.policies.clear.clear_policy import ClearPolicy
    from continual_rl.policies.clear.clear_policy_config import ClearPolicyConfig
    return PolicyStruct(ClearPolicy, ClearPolicyConfig)


def get_available_policies():
    """
    The registry of policies that are available for ease of use. To create your own, duplicate prototype_policy's
    folder, populate it (reference policy_base.py as necessary), and add it here.
    """
    policies = LazyDict({"discrete_random": load_discrete_random,
                         "ppo": load_ppo,
                         "impala": load_impala,
                         "clear": load_clear})

    return policies
