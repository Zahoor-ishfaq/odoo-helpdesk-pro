"""Tests for helpdesk.stage.mail_template_id: the stage-entry email."""

# pylint: disable=import-error
# odoo is not installed in the isolated pylint-odoo pre-commit environment.
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestHelpdeskStageEmail(TransactionCase):
    """Moving a ticket into a stage with a template posts that template."""

    @classmethod
    def setUpClass(cls):  # pylint: disable=invalid-name
        """A team, a templated open stage and a plain open stage."""
        super().setUpClass()
        cls.team = cls.env["helpdesk.team"].create(
            {"name": "Stage Email Team", "csat_enabled": False}
        )
        # pylint: disable=protected-access
        cls.template = cls.env["mail.template"].create(
            {
                "name": "Stage: Waiting on you",
                "model_id": cls.env["ir.model"]._get("helpdesk.ticket").id,
                "subject": "Waiting on you ({{ object.ref }})",
                "email_to": "{{ object.partner_email }}",
                "body_html": "<p>We need more details from you.</p>",
            }
        )
        cls.templated_stage = cls.env["helpdesk.stage"].create(
            {
                "name": "Waiting on Customer",
                "sequence": 25,
                "mail_template_id": cls.template.id,
            }
        )
        cls.plain_stage = cls.env["helpdesk.stage"].create(
            {"name": "Plain Stage", "sequence": 26}
        )
        cls.partner = cls.env["res.partner"].create(
            {"name": "Stage Customer", "email": "stage@example.com"}
        )

    def _create_ticket(self, **vals):
        return self.env["helpdesk.ticket"].create(
            {
                "name": "Stage email ticket",
                "team_id": self.team.id,
                "partner_id": self.partner.id,
                "partner_email": self.partner.email,
                **vals,
            }
        )

    def _stage_messages(self, ticket):
        return ticket.message_ids.filtered(
            lambda m: "We need more details" in (m.body or "")
        )

    def test_entering_templated_stage_posts_template(self):
        """The template's subject/body land in the ticket's chatter."""
        ticket = self._create_ticket()
        ticket.stage_id = self.templated_stage
        messages = self._stage_messages(ticket)
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages.subject, f"Waiting on you ({ticket.ref})")
        self.assertEqual(messages.subtype_id, self.env.ref("mail.mt_comment"))

    def test_same_stage_again_sends_nothing(self):
        """Re-writing the current stage is not a transition."""
        ticket = self._create_ticket()
        ticket.stage_id = self.templated_stage
        ticket.write({"stage_id": self.templated_stage.id})
        self.assertEqual(len(self._stage_messages(ticket)), 1)

    def test_stage_without_template_sends_nothing(self):
        """A stage with no template posts no customer message."""
        ticket = self._create_ticket()
        before = ticket.message_ids.filtered(
            lambda m: m.subtype_id == self.env.ref("mail.mt_comment")
        )
        ticket.stage_id = self.plain_stage
        after = ticket.message_ids.filtered(
            lambda m: m.subtype_id == self.env.ref("mail.mt_comment")
        )
        self.assertEqual(before, after)

    def test_no_partner_no_email_skipped(self):
        """With nobody to write to, the stage change still works, silently."""
        ticket = self.env["helpdesk.ticket"].create(
            {"name": "Anonymous", "team_id": self.team.id}
        )
        ticket.stage_id = self.templated_stage
        self.assertEqual(ticket.stage_id, self.templated_stage)
        self.assertFalse(self._stage_messages(ticket))

    def test_skip_stage_email_context(self):
        """skip_stage_email suppresses the template."""
        ticket = self._create_ticket()
        ticket.with_context(skip_stage_email=True).stage_id = self.templated_stage
        self.assertFalse(self._stage_messages(ticket))

    def test_merge_source_gets_no_stage_email(self):
        """Closing a merged-away ticket doesn't email its customer."""
        closed_stage = self.env["helpdesk.stage"].search(
            [("is_closed", "=", True)], order="sequence", limit=1
        )
        closed_stage.mail_template_id = self.template
        destination = self._create_ticket(name="Destination")
        source = self._create_ticket(name="Source")
        self.env["helpdesk.ticket.merge"].create(
            {"destination_ticket_id": destination.id, "source_ticket_id": source.id}
        ).action_merge()
        self.assertTrue(source.stage_id.is_closed)
        self.assertFalse(self._stage_messages(source))
        self.assertFalse(self._stage_messages(destination))
