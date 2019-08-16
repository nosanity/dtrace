import logging
from datetime import datetime
from django.conf import settings
from django.utils import timezone
from carrier_client.manager import MessageManager, MessageManagerException
from carrier_client.message import OutgoingMessage
from django_carrier_client.helpers import MessageManagerHelper
from isle.api import SSOApi, ApiError
from isle.models import LabsUserResult, LabsTeamResult, PLEUserResult
from isle.utils import update_casbin_data, create_or_update_competence, create_or_update_metamodel, \
    create_or_update_context, create_or_update_activity, delete_activity, create_or_update_run, delete_run, \
    create_or_update_event, delete_event, update_event_blocks, create_or_update_event_entry, delete_run_enrollment, \
    create_or_update_run_enrollment, create_or_update_team


message_manager = MessageManager(
    topics=[settings.KAFKA_TOPIC],
    host=settings.KAFKA_HOST,
    port=settings.KAFKA_PORT,
    protocol=settings.KAFKA_PROTOCOL,
    auth=settings.KAFKA_TOKEN,
)


class KafkaActions:
    CREATE = 'create'
    UPDATE = 'update'
    DELETE = 'delete'


def get_payload(obj, obj_id, action):
    def for_type(payload_type):
        return {
            'action': action,
            'type': payload_type,
            'id': {
                payload_type: {'id': obj_id}
            },
            'timestamp': datetime.isoformat(timezone.now()),
            'title': str(obj),
            'source': settings.KAFKA_TOPIC,
            'version': None,
        }
    if isinstance(obj, LabsUserResult):
        return for_type('user_result')
    if isinstance(obj, LabsTeamResult):
        return for_type('team_result')
    if isinstance(obj, PLEUserResult):
        return for_type('user_result_ple')


def send_object_info(obj, obj_id, action):
    """
    отправка в кафку сообщения, составленного исходя из типа объекта obj и действия
    """
    if not getattr(settings, 'KAFKA_HOST'):
        logging.warning('KAFKA_HOST is not defined')
        return
    payload = get_payload(obj, obj_id, action)
    if not payload:
        logging.error("Can't get payload for %s action %s" % (obj, action))
        return
    outgoing_message = OutgoingMessage(
        topic=settings.KAFKA_TOPIC,
        payload=payload
    )
    try:
        message_manager.send_one(outgoing_message)
    except Exception:
        logging.exception('Kafka communication failed with payload %s' % payload)


def check_kafka():
    return False


class KafkaBaseListener:
    topic = ''
    actions = []
    msg_type = ''

    def handle_message(self, msg):
        if msg.get_topic() == self.topic:
            try:
                payload = msg.get_payload()
                if payload.get('type') == self.msg_type and payload.get('action') in self.actions and payload.get('id'):
                    self._handle_for_id(payload['id'], payload['action'])
            except MessageManagerException:
                logging.error('Got incorrect json from kafka: %s' % msg._value)

    def _handle_for_id(self, obj_id, action):
        raise NotImplementedError


class SSOUserChangeListener(KafkaBaseListener):
    topic = settings.KAFKA_TOPIC_SSO
    actions = (KafkaActions.CREATE, KafkaActions.UPDATE)
    msg_type = 'user'

    def _handle_for_id(self, obj_id, action):
        try:
            assert isinstance(obj_id, dict)
            user_id = obj_id.get('user', {}).get('id')
            try:
                SSOApi().push_user_to_uploads(user_id)
            except ApiError:
                pass
        except (AssertionError, AttributeError):
            logging.error('Got wrong object id from kafka: %s' % obj_id)


class CasbinPolicyListener(KafkaBaseListener):
    topic = settings.KAFKA_TOPIC_SSO
    actions = (KafkaActions.CREATE, KafkaActions.DELETE, KafkaActions.UPDATE)
    msg_type = 'casbin_policy'

    def _handle_for_id(self, obj_id, action):
        update_casbin_data()


class CasbinModelListener(KafkaBaseListener):
    topic = settings.KAFKA_TOPIC_SSO
    actions = (KafkaActions.CREATE, KafkaActions.UPDATE)
    msg_type = 'casbin_model'

    def _handle_for_id(self, obj_id, action):
        update_casbin_data()


class DPModelListener(KafkaBaseListener):
    topic = settings.KAFKA_TOPIC_LABS
    actions = [KafkaActions.CREATE, KafkaActions.UPDATE]
    msg_type = 'model'

    def _handle_for_id(self, obj_id, action):
        try:
            model_uuid = obj_id.get(self.msg_type).get('uuid')
            assert model_uuid, 'failed to get model uuid from %s' % obj_id
            create_or_update_metamodel(model_uuid)
        except (AssertionError, AttributeError):
            logging.exception('Got wrong object id from kafka: %s' % obj_id)


class DPCompetenceListener(KafkaBaseListener):
    topic = settings.KAFKA_TOPIC_LABS
    actions = [KafkaActions.CREATE, KafkaActions.UPDATE]
    msg_type = 'competence'

    def _handle_for_id(self, obj_id, action):
        try:
            competence_uuid = obj_id.get(self.msg_type).get('uuid')
            assert competence_uuid, 'failed to get competence uuid from %s' % obj_id
            create_or_update_competence(competence_uuid)
        except (AssertionError, AttributeError):
            logging.exception('Got wrong object id from kafka: %s' % obj_id)


class LABSContextListener(KafkaBaseListener):
    topic = settings.KAFKA_TOPIC_LABS
    actions = [KafkaActions.CREATE, KafkaActions.UPDATE]
    msg_type = 'context'

    def _handle_for_id(self, obj_id, action):
        try:
            context_uuid = obj_id.get(self.msg_type).get('uuid')
            assert context_uuid, 'failed to get context uuid from %s' % obj_id
            create_or_update_context(context_uuid)
        except (AssertionError, AttributeError):
            logging.exception('Got wrong object id from kafka: %s' % obj_id)


class LABSActivityListener(KafkaBaseListener):
    topic = settings.KAFKA_TOPIC_LABS
    actions = [KafkaActions.CREATE, KafkaActions.UPDATE, KafkaActions.DELETE]
    msg_type = 'activity'

    def _handle_for_id(self, obj_id, action):
        try:
            activity_uuid = obj_id.get(self.msg_type).get('uuid')
            assert activity_uuid, 'failed to get activity uuid from %s' % obj_id
            if action != KafkaActions.DELETE:
                create_or_update_activity(activity_uuid)
            else:
                delete_activity(activity_uuid)
        except (AssertionError, AttributeError):
            logging.exception('Got wrong object id from kafka: %s' % obj_id)


class LABSRunListener(KafkaBaseListener):
    topic = settings.KAFKA_TOPIC_LABS
    actions = [KafkaActions.CREATE, KafkaActions.UPDATE, KafkaActions.DELETE]
    msg_type = 'run'

    def _handle_for_id(self, obj_id, action):
        try:
            run_uuid = obj_id.get(self.msg_type).get('uuid')
            assert run_uuid, 'failed to get run uuid from %s' % obj_id
            if action != KafkaActions.DELETE:
                create_or_update_run(run_uuid)
            else:
                delete_run(run_uuid)
        except (AssertionError, AttributeError):
            logging.exception('Got wrong object id from kafka: %s' % obj_id)


class LABSEventListener(KafkaBaseListener):
    topic = settings.KAFKA_TOPIC_LABS
    actions = [KafkaActions.CREATE, KafkaActions.UPDATE, KafkaActions.DELETE]
    msg_type = 'event'

    def _handle_for_id(self, obj_id, action):
        try:
            event_uuid = obj_id.get(self.msg_type).get('uuid')
            assert event_uuid, 'failed to get event uuid from %s' % obj_id
            if action != KafkaActions.DELETE:
                create_or_update_event(event_uuid)
            else:
                delete_event(event_uuid)
        except (AssertionError, AttributeError):
            logging.exception('Got wrong object id from kafka: %s' % obj_id)


class LABSEventBlockListener(KafkaBaseListener):
    topic = settings.KAFKA_TOPIC_LABS
    actions = [KafkaActions.CREATE, KafkaActions.UPDATE, KafkaActions.DELETE]
    msg_type = 'block'

    def _handle_for_id(self, obj_id, action):
        try:
            event_uuid = obj_id.get('event', {}).get('uuid')
            assert event_uuid, 'failed to get event uuid from %s' % obj_id
            update_event_blocks(event_uuid)
        except (AssertionError, AttributeError):
            logging.exception('Got wrong object id from kafka: %s' % obj_id)


class XLECheckinListener(KafkaBaseListener):
    topic = settings.KAFKA_TOPIC_XLE
    actions = [KafkaActions.CREATE, KafkaActions.UPDATE]
    msg_type = 'checkin'

    def _handle_for_id(self, obj_id, action):
        try:
            entry_uuid = obj_id.get(self.msg_type).get('uuid')
            assert entry_uuid, 'failed to get checkin uuid from %s' % obj_id
            create_or_update_event_entry(entry_uuid)
        except (AssertionError, AttributeError):
            logging.exception('Got wrong object id from kafka: %s' % obj_id)


class XLERunEnrollmentListener(KafkaBaseListener):
    topic = settings.KAFKA_TOPIC_XLE
    actions = [KafkaActions.CREATE, KafkaActions.UPDATE, KafkaActions.DELETE]
    msg_type = 'timetable'

    def _handle_for_id(self, obj_id, action):
        try:
            run_uuid = obj_id.get(self.msg_type).get('run_uuid')
            unti_id = obj_id.get(self.msg_type).get('unti_id')
            assert run_uuid and unti_id, 'failed to get timetable data from %s' % obj_id
            if action == KafkaActions.DELETE:
                delete_run_enrollment(run_uuid, unti_id)
            else:
                create_or_update_run_enrollment(run_uuid, unti_id)
        except (AssertionError, AttributeError):
            logging.exception('Got wrong object id from kafka: %s' % obj_id)


class PTTeamListener(KafkaBaseListener):
    topic = settings.KAFKA_TOPIC_PT
    actions = [KafkaActions.CREATE, KafkaActions.UPDATE]
    msg_type = 'team'

    def _handle_for_id(self, obj_id, action):
        try:
            team_uuid = obj_id.get(self.msg_type).get('uuid')
            assert team_uuid, 'failed to get team uuid from %s' % obj_id
            create_or_update_team(team_uuid)
        except (AssertionError, AttributeError):
            logging.exception('Got wrong object id from kafka: %s' % obj_id)


MessageManagerHelper.set_manager_to_listen(SSOUserChangeListener())
MessageManagerHelper.set_manager_to_listen(CasbinPolicyListener())
MessageManagerHelper.set_manager_to_listen(CasbinModelListener())
MessageManagerHelper.set_manager_to_listen(DPModelListener())
MessageManagerHelper.set_manager_to_listen(DPCompetenceListener())
MessageManagerHelper.set_manager_to_listen(LABSContextListener())
MessageManagerHelper.set_manager_to_listen(LABSActivityListener())
MessageManagerHelper.set_manager_to_listen(LABSRunListener())
MessageManagerHelper.set_manager_to_listen(LABSEventListener())
MessageManagerHelper.set_manager_to_listen(LABSEventBlockListener())
MessageManagerHelper.set_manager_to_listen(XLECheckinListener())
MessageManagerHelper.set_manager_to_listen(XLERunEnrollmentListener())
MessageManagerHelper.set_manager_to_listen(PTTeamListener())
