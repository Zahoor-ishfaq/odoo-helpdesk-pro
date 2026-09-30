"""Tests for the public CSAT rating endpoint: token validation and window."""

from datetime import timedelta

# pylint: disable=import-error
# odoo is not installed in the isolated pylint-odoo pre-commit environment.
from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import HttpCase

from .common import make_mon_fri_calendar


@tagged("post_install", "-at_install")
class TestHelpdeskRating(HttpCase):
    """Signed-token CSAT rating: confirm page / valid / tampered / window."""

    @classmethod
    def setUpClass(cls):  # pylint: disable=invalid-name
        """A closed ticket with its rating_token already generated."""
        super().setUpClass()
        calendar = make_mon_fri_calendar(cls.env, name="Rating test calendar")
        team = cls.env["helpdesk.team"].create(
            {"name": "Rating Team", "calendar_id": calendar.id, "csat_enabled": True}
        )
        closed_stage = cls.env["helpdesk.stage"].search(
            [("is_closed", "=", True)], limit=1
        )
        cls.ticket = cls.env["helpdesk.ticket"].create(
            {
                "name": "Rate me",
                "team_id": team.id,
                "partner_email": "customer@example.com",
            }
        )
        cls.ticket.stage_id = closed_stage

    def _link(self, rating, token=None):
        """The GET link exactly as the CSAT email renders it."""
        token = token or self.ticket.rating_token
        return f"/helpdesk/rate/{self.ticket.id}/{token}/{rating}"

    def _submit(self, rating, token=None):
        """POST the confirmation form, as the customer's browser would."""
        token = token or self.ticket.rating_token
        return self.url_open(
            f"/helpdesk/rate/{self.ticket.id}/{token}/submit",
            data={"rating": rating},
        )

    def test_get_shows_confirm_page_without_writing(self):
        """Opening an email link only renders the confirm form."""
        response = self.url_open(self._link("good"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("/submit", response.text)
        self.ticket.invalidate_recordset(["rating", "rating_date"])
        self.assertFalse(self.ticket.rating)
        self.assertFalse(self.ticket.rating_date)

    def test_link_scanner_visiting_every_link_records_nothing(self):
        """A mail scanner fetching all three links leaves the rating empty."""
        for rating in ("good", "okay", "bad"):
            response = self.url_open(self._link(rating))
            self.assertEqual(response.status_code, 200)
        self.ticket.invalidate_recordset(["rating", "rating_date"])
        self.assertFalse(self.ticket.rating)
        self.assertFalse(self.ticket.rating_date)

    def test_valid_token_records_rating(self):
        """Submitting the confirm form with a correct token records the rating."""
        self.assertTrue(self.ticket.rating_token)
        response = self._submit("good")
        self.assertEqual(response.status_code, 200)
        self.ticket.invalidate_recordset(["rating", "rating_date"])
        self.assertEqual(self.ticket.rating, "good")
        self.assertTrue(self.ticket.rating_date)

    def test_tampered_token_rejected(self):
        """A wrong token renders the invalid page and changes nothing."""
        response = self.url_open(self._link("good", token="not-the-real-token"))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("/submit", response.text)

        response = self._submit("good", token="not-the-real-token")
        self.assertEqual(response.status_code, 200)
        self.assertIn("not valid", response.text)
        self.ticket.invalidate_recordset(["rating"])
        self.assertFalse(self.ticket.rating)

    def test_invalid_rating_value_rejected(self):
        """A POST with a rating outside good/okay/bad writes nothing."""
        response = self._submit("excellent")
        self.assertEqual(response.status_code, 200)
        self.assertIn("not valid", response.text)
        self.ticket.invalidate_recordset(["rating", "rating_date"])
        self.assertFalse(self.ticket.rating)
        self.assertFalse(self.ticket.rating_date)

    def test_second_rating_within_window_updates(self):
        """A repeat submit inside the window updates the value, not the anchor."""
        self._submit("bad")
        self.ticket.invalidate_recordset(["rating", "rating_date"])
        self.assertEqual(self.ticket.rating, "bad")
        first_rating_date = self.ticket.rating_date

        self._submit("good")
        self.ticket.invalidate_recordset(["rating", "rating_date"])
        self.assertEqual(self.ticket.rating, "good")
        self.assertEqual(
            self.ticket.rating_date,
            first_rating_date,
            "the window's anchor shouldn't move on an update",
        )

    def test_rating_locked_after_window(self):
        """Past the update window, neither the link nor a submit changes it."""
        self.ticket.write(
            {
                "rating": "bad",
                "rating_date": fields.Datetime.now() - timedelta(days=8),
            }
        )
        response = self.url_open(self._link("good"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("can no longer be changed", response.text)
        self.assertNotIn("/submit", response.text)

        response = self._submit("good")
        self.assertEqual(response.status_code, 200)
        self.assertIn("can no longer be changed", response.text)
        self.ticket.invalidate_recordset(["rating"])
        self.assertEqual(
            self.ticket.rating, "bad", "a locked rating must not be overwritten"
        )
