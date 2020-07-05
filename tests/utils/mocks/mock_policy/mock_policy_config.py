from continual_rl.utils.config_base import ConfigBase


class MockPolicyConfig(ConfigBase):

    def __init__(self):
        super().__init__()
        self.test_param = "unfilled"
        self.test_param_2 = "also unfilled"

    def _load_from_dict_internal(self, config_json):
        self.test_param = config_json.pop("test_param", self.test_param)
        self.test_param_2 = config_json.pop("test_param_2", self.test_param_2)

        return self
