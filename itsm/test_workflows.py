from datetime import timedelta
from io import StringIO

from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from assets.models import Asset
from changes.models import ChangeRequest, ChangeApproval
from incidents.models import Incident
from tickets.models import Ticket, SLAPolicy, TicketSLA, TicketComment
from tickets.sla_service import attach_sla, check_sla_breaches, record_first_response
from users.models import User

TEST_SETTINGS = override_settings(
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    },
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
)

CHANGE_FIELDS = dict(
    title='c', description='d', justification='j',
    implementation_plan='i', rollback_plan='r',
)


@TEST_SETTINGS
class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        mk = User.objects.create_user
        cls.admin = mk('admin1', 'admin@x.com', 'pw', role='admin')
        cls.agent = mk('agent1', 'agent@x.com', 'pw', role='agent')
        cls.user = mk('user1', 'user@x.com', 'pw', role='end_user')
        cls.other = mk('user2', 'other@x.com', 'pw', role='end_user')

    def login(self, u):
        self.client.force_login(u)

    def make_change(self, **kw):
        d = dict(CHANGE_FIELDS, requested_by=self.user)
        d.update(kw)
        return ChangeRequest.objects.create(**d)


class TicketFlow(Base):
    def test_create_attaches_sla(self):
        SLAPolicy.objects.create(priority='high', response_time_minutes=60, resolution_time_minutes=240)
        self.login(self.user)
        r = self.client.post('/tickets/create/', {
            'title': 'VPN down', 'description': 'cannot connect', 'priority': 'high'})
        self.assertEqual(r.status_code, 302)
        t = Ticket.objects.get()
        self.assertEqual(t.created_by, self.user)
        self.assertTrue(TicketSLA.objects.filter(ticket=t).exists())
        self.assertEqual(len(mail.outbox), 1)  # requester confirmation
        self.assertIn('TKT-', mail.outbox[0].subject)

    def test_end_user_cannot_see_others_tickets(self):
        t = Ticket.objects.create(title='a', description='b', created_by=self.other)
        self.login(self.user)
        self.assertEqual(self.client.get(f'/tickets/{t.pk}/').status_code, 302)

    def test_resolve_requires_post_and_agent(self):
        t = Ticket.objects.create(title='a', description='b', created_by=self.user)
        self.login(self.agent)
        self.assertEqual(self.client.get(f'/tickets/{t.pk}/resolve/').status_code, 405)
        t.refresh_from_db()
        self.assertEqual(t.status, 'open')
        self.client.post(f'/tickets/{t.pk}/resolve/')
        t.refresh_from_db()
        self.assertEqual(t.status, 'resolved')
        self.assertIsNotNone(t.resolved_at)
        self.assertTrue(t.history.filter(field_changed='status').exists())
        self.assertEqual(len(mail.outbox), 1)  # resolution notice to requester

        t2 = Ticket.objects.create(title='c', description='d', created_by=self.user)
        self.login(self.user)
        self.client.post(f'/tickets/{t2.pk}/resolve/')
        t2.refresh_from_db()
        self.assertEqual(t2.status, 'open')

    def test_edit_to_resolved_sets_resolved_at(self):
        t = Ticket.objects.create(title='a', description='b', created_by=self.user)
        self.login(self.agent)
        self.client.post(f'/tickets/{t.pk}/edit/', {
            'title': 'a', 'description': 'b', 'priority': 'medium', 'status': 'resolved'})
        t.refresh_from_db()
        self.assertEqual(t.status, 'resolved')
        self.assertIsNotNone(t.resolved_at)

    def test_internal_comment_hidden_from_end_user(self):
        t = Ticket.objects.create(title='a', description='b', created_by=self.user)
        TicketComment.objects.create(ticket=t, author=self.agent, body='SECRET-NOTE', is_internal=True)
        self.login(self.user)
        self.assertNotContains(self.client.get(f'/tickets/{t.pk}/'), 'SECRET-NOTE')
        self.login(self.agent)
        self.assertContains(self.client.get(f'/tickets/{t.pk}/'), 'SECRET-NOTE')

    def test_end_user_cannot_post_internal_comment(self):
        t = Ticket.objects.create(title='a', description='b', created_by=self.user)
        self.login(self.user)
        self.client.post(f'/tickets/{t.pk}/', {'body': 'hi', 'is_internal': 'on'})
        self.assertFalse(t.comments.get().is_internal)


class SLA(Base):
    def setUp(self):
        SLAPolicy.objects.create(priority='medium', response_time_minutes=30, resolution_time_minutes=60)

    def test_no_policy_is_noop(self):
        t = Ticket.objects.create(title='a', description='b', priority='low', created_by=self.user)
        attach_sla(t)
        self.assertFalse(TicketSLA.objects.exists())
        record_first_response(t, self.agent)  # must not raise

    def test_first_response_recorded_once(self):
        t = Ticket.objects.create(title='a', description='b', created_by=self.user)
        attach_sla(t)
        record_first_response(t, self.user)  # end users do not count
        t.sla.refresh_from_db()
        self.assertIsNone(t.sla.first_response_at)
        record_first_response(t, self.agent)
        t.sla.refresh_from_db()
        first = t.sla.first_response_at
        self.assertIsNotNone(first)
        record_first_response(t, self.admin)
        t.sla.refresh_from_db()
        self.assertEqual(t.sla.first_response_at, first)

    def test_late_response_marks_breach(self):
        t = Ticket.objects.create(title='a', description='b', created_by=self.user)
        attach_sla(t)
        TicketSLA.objects.filter(ticket=t).update(response_due=timezone.now() - timedelta(minutes=1))
        t = Ticket.objects.get(pk=t.pk)
        record_first_response(t, self.agent)
        t.sla.refresh_from_db()
        self.assertTrue(t.sla.response_breached)

    def test_breach_check_idempotent_and_skips_resolved(self):
        late = Ticket.objects.create(title='late', description='b', created_by=self.user, assigned_to=self.agent)
        done = Ticket.objects.create(title='done', description='b', created_by=self.user, status='resolved')
        attach_sla(late)
        attach_sla(done)
        TicketSLA.objects.update(resolution_due=timezone.now() - timedelta(minutes=5))
        self.assertEqual(check_sla_breaches(), 1)
        self.assertEqual(check_sla_breaches(), 0)
        self.assertTrue(TicketSLA.objects.get(ticket=late).breach_notified)
        self.assertGreaterEqual(len(mail.outbox), 1)
        self.assertFalse(TicketSLA.objects.get(ticket=done).resolution_breached)

    def test_warning_sent_once_before_breach(self):
        t = Ticket.objects.create(title='w', description='b', created_by=self.user, assigned_to=self.agent)
        attach_sla(t)
        # 85% of the 60-minute window elapsed, warning threshold is 80%
        Ticket.objects.filter(pk=t.pk).update(created_at=timezone.now() - timedelta(minutes=51))
        self.assertEqual(check_sla_breaches(), 0)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('SLA WARNING', mail.outbox[0].subject)
        check_sla_breaches()
        self.assertEqual(len(mail.outbox), 1)

    def test_management_command(self):
        out = StringIO()
        call_command('check_sla', stdout=out)
        self.assertIn('0 newly breached', out.getvalue())


class IncidentFlow(Base):
    def test_end_user_cannot_create(self):
        self.login(self.user)
        self.client.post('/incidents/create/', {
            'title': 'x', 'description': 'y', 'severity': 'sev3', 'status': 'open'})
        self.assertFalse(Incident.objects.exists())

    def test_resolving_via_update_sets_resolved_at(self):
        self.login(self.agent)
        self.client.post('/incidents/create/', {
            'title': 'x', 'description': 'y', 'severity': 'sev2', 'status': 'open'})
        inc = Incident.objects.get()
        self.client.post(f'/incidents/{inc.pk}/', {'message': 'fixed', 'new_status': 'resolved'})
        inc.refresh_from_db()
        self.assertEqual(inc.status, 'resolved')
        self.assertIsNotNone(inc.resolved_at)
        self.assertEqual(inc.updates.count(), 2)


class ChangeFlow(Base):
    def test_submit_requires_post_and_owner(self):
        c = self.make_change()
        self.login(self.user)
        self.assertEqual(self.client.get(f'/changes/{c.pk}/submit/').status_code, 405)
        self.login(self.other)
        self.assertEqual(self.client.post(f'/changes/{c.pk}/submit/').status_code, 404)
        self.login(self.user)
        self.client.post(f'/changes/{c.pk}/submit/')
        c.refresh_from_db()
        self.assertEqual(c.status, 'submitted')

    def test_other_user_cannot_view_or_edit(self):
        c = self.make_change()
        self.login(self.other)
        self.assertEqual(self.client.get(f'/changes/{c.pk}/').status_code, 302)
        self.client.post(f'/changes/{c.pk}/edit/', {
            'title': 'HACK', 'description': 'd', 'change_type': 'normal', 'risk_level': 'low',
            'justification': 'j', 'implementation_plan': 'i', 'rollback_plan': 'r'})
        c.refresh_from_db()
        self.assertEqual(c.title, 'c')

    def test_admin_approves_and_non_admin_cannot(self):
        c = self.make_change(status='submitted')
        self.login(self.agent)
        self.client.post(f'/changes/{c.pk}/', {'decision': 'approved', 'comments': ''})
        self.assertFalse(ChangeApproval.objects.exists())
        self.login(self.admin)
        self.client.post(f'/changes/{c.pk}/', {'decision': 'approved', 'comments': 'ok'})
        c.refresh_from_db()
        self.assertEqual(c.status, 'approved')
        self.assertEqual(c.approved_by, self.admin)
        self.assertEqual(len(mail.outbox), 1)

    def test_reject(self):
        c = self.make_change(status='submitted')
        self.login(self.admin)
        self.client.post(f'/changes/{c.pk}/', {'decision': 'rejected', 'comments': 'no'})
        c.refresh_from_db()
        self.assertEqual(c.status, 'rejected')


class AssetFlow(Base):
    def test_retire_post_only(self):
        a = Asset.objects.create(name='L', asset_tag='A1', serial_number='S1',
                                 status='in_use', assigned_to=self.user)
        self.login(self.agent)
        self.assertEqual(self.client.get(f'/assets/{a.pk}/retire/').status_code, 405)
        self.client.post(f'/assets/{a.pk}/retire/')
        a.refresh_from_db()
        self.assertEqual(a.status, 'retired')
        self.assertIsNone(a.assigned_to)
        self.assertEqual(a.history.count(), 1)

    def test_end_user_cannot_create(self):
        self.login(self.user)
        self.client.post('/assets/create/', {
            'name': 'x', 'asset_tag': 'T', 'asset_type': 'hardware', 'status': 'available'})
        self.assertFalse(Asset.objects.exists())


class ApiFlow(Base):
    def post_json(self, url, data):
        return self.client.post(url, data, content_type='application/json')

    def test_requires_auth(self):
        self.assertIn(self.client.get('/api/tickets/').status_code, (401, 403))

    def test_end_user_scoped_and_cannot_modify(self):
        mine = Ticket.objects.create(title='m', description='d', created_by=self.user)
        Ticket.objects.create(title='o', description='d', created_by=self.other)
        self.login(self.user)
        data = self.client.get('/api/tickets/').json()
        rows = data['results'] if isinstance(data, dict) else data
        self.assertEqual([r['title'] for r in rows], ['m'])
        r = self.client.patch(f'/api/tickets/{mine.pk}/', {'status': 'closed'}, content_type='application/json')
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.client.delete(f'/api/tickets/{mine.pk}/').status_code, 403)

    def test_end_user_cannot_create_incident(self):
        self.login(self.user)
        r = self.post_json('/api/incidents/', {'title': 'x', 'description': 'y', 'severity': 'sev3'})
        self.assertEqual(r.status_code, 403)

    def test_api_ticket_create_and_resolve(self):
        self.login(self.user)
        r = self.post_json('/api/tickets/', {'title': 't', 'description': 'd', 'priority': 'low'})
        self.assertEqual(r.status_code, 201, r.content)
        pk = r.json()['id']
        self.assertEqual(self.client.post(f'/api/tickets/{pk}/resolve/').status_code, 403)
        self.login(self.agent)
        self.assertEqual(self.client.post(f'/api/tickets/{pk}/resolve/').status_code, 200)
        self.assertEqual(self.client.post(f'/api/tickets/{pk}/resolve/').status_code, 400)

    def test_api_change_approval_rules(self):
        c = self.make_change(status='submitted')
        url = f'/api/changes/{c.pk}/approve/'
        self.login(self.agent)
        self.assertEqual(self.post_json(url, {'decision': 'approved'}).status_code, 403)
        self.login(self.admin)
        self.assertEqual(self.post_json(url, {'decision': 'bogus'}).status_code, 400)
        # abstaining must not reject the change
        self.assertEqual(self.post_json(url, {'decision': 'abstained'}).status_code, 200)
        c.refresh_from_db()
        self.assertEqual(c.status, 'submitted')
        self.assertEqual(self.post_json(url, {'decision': 'approved'}).status_code, 409)

    def test_api_cannot_approve_draft(self):
        c = self.make_change()
        self.login(self.admin)
        r = self.post_json(f'/api/changes/{c.pk}/approve/', {'decision': 'approved'})
        self.assertEqual(r.status_code, 400)

    def test_api_end_user_cannot_edit_submitted_change(self):
        c = self.make_change(status='submitted')
        self.login(self.user)
        r = self.client.patch(f'/api/changes/{c.pk}/', {'title': 'new'}, content_type='application/json')
        self.assertEqual(r.status_code, 403)

    def test_schema_generates(self):
        self.login(self.user)
        self.assertEqual(self.client.get('/api/schema/').status_code, 200)
