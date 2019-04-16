from casbin import persist
from casbin.model import Model
from casbin.persist.adapter import Adapter
from .models import CasbinModel, CasbinPolicy
from .utils import update_casbin_data


def get_casbin_model():
    # from django.conf import settings
    # import os
    # return os.path.join(settings.BASE_DIR, 'model.abac')
    txt = '''
[request_definition]
r = sub, obj, act

[policy_definition]
p = sub, obj, act

[policy_effect]
e = some(where (p.eft == allow))

[matchers]
m = r.sub == r.obj.uuid
    '''
    m = Model()
    # m.load_model_from_text(txt)
    m.load_model_from_text(CasbinModel.objects.get().config)
    return m


class TextAdapter(Adapter):
    def __init__(self, policy):
        self.policy = policy
        # print('------------policy')
        # print(policy)

    def load_policy(self, model):
        for line in self.policy.splitlines():
            if not line.strip():
                continue
            persist.load_policy_line(line.strip(), model)

def get_casbin_policy():
    # from .api import SSOApi
    # d = SSOApi().get_policy()['data']
    # print('------sso resp')
    # print(d)
    # return TextAdapter(d)
    return TextAdapter(CasbinPolicy.objects.first().policy)


def get_enforcer():
    from casbin.enforcer import Enforcer
    try:
        model = get_casbin_model()
    except CasbinModel.DoesNotExist:
        if not update_casbin_data():
            return
        model = get_casbin_model()
    return Enforcer(model, get_casbin_policy())


def enforce(sub, obj, action='read'):
    enforcer = get_enforcer()
    if not enforcer:
        return False
    return enforcer.enforce(sub, obj, action)
