from django.core.management.base import BaseCommand
from django.conf import settings
import os
from django.core.cache import caches
from casbin.enforcer import Enforcer
c = caches['default']
from isle.models import Context


class Command(BaseCommand):
    def handle(self, *args, **options):
        # p = os.path.join(settings.BASE_DIR, 'policy2.csv')
        # default_role_perms = [
        #     ['p', 'assistant', 'file', 'upload', 'allow'],
        #     ['p', 'curator', 'users', 'edit', 'allow'],
        #     ['p', 'curator', 'users', 'view', 'allow'],
        #     ['p', 'somerole', 'someobject', 'view', 'allow'],
        #     ['p', 'somerole', 'someobject', 'write', 'allow'],
        #
        # ]
        # with open(p, 'w') as f:
        #     for c in Context.objects.all():
        #         if c.parent:
        #             f.write(', '.join(['g2', c.uuid, c.parent.uuid]) + '\n')
        #         for item in default_role_perms:
        #             tmp = item[:2] + [c.uuid] + item[2:]
        #             f.write(', '.join(tmp) + '\n')
        #
        #     context_uuids = list(Context.objects.values_list('uuid', flat=True))
        #     import random
        #     for unti_id in range(1, 1000):
        #         roles = list(set([i[1] for i in default_role_perms]))
        #         for context in random.sample(context_uuids, random.randint(1, 10)):
        #             num_roles = lambda: 1 if random.random() > .35 else (2 if random.random() > .3 else 3)
        #             user_roles = random.sample(roles, num_roles())
        #             for r in user_roles:
        #                 f.write(', '.join(['g', str(unti_id), r, context]) + '\n')
        self.test_time()


    def test_time(self):
        from time import time
        t = time()
        e = self.get_from_cache()
        import pdb;pdb.set_trace()
        print(e.enforce('user', 'context11', 'file', 'upload'))
        print('no cache: %s' % (time() - t))
        t = time()
        e = self.get_from_cache()
        print(e.enforce('user', 'context11', 'file', 'upload'))
        print('with cache: %s' % (time() - t))
        import pickle
        from io import BytesIO
        print('enforcer size', BytesIO().write(pickle.dumps(e)) / 1024)

    def create_data(self):
        pass

    def create_users(self):
        pass

    def test_enforcer(self):
        print(e.enforce('user', 'context1', 'upload'))
        print(e.enforce('user', 'context11', 'upload'))
        print(e.enforce('user2', 'context1', 'upload'))

    def get_enforcer(self):
        print('create enforcer')
        return Enforcer(
            os.path.join(settings.BASE_DIR, 'isle/management/commands/model.conf'),
            # os.path.join(settings.BASE_DIR, 'isle/management/commands/policy.csv'),
            os.path.join(settings.BASE_DIR, 'policy2.csv'),
        )

    def get_from_cache(self):
        key = 'enforcer8'
        e = c.get(key)
        if e:
            return e
        e = self.get_enforcer()
        c.set(key, e)
        return e