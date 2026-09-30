"""Public CSAT rating endpoint: no login required, signed-token access."""

# pylint: disable=import-error
# odoo is not installed in the isolated pylint-odoo pre-commit environment.
from odoo import http
from odoo.http import request

VALID_RATINGS = ("good", "okay", "bad")
PAGE = "helpdesk_community_pro.rating_feedback_page"


class HelpdeskRating(http.Controller):
    """Two-step satisfaction rating, reached from the CSAT email.

    The email links only render a confirmation page (GET, no write); the
    rating is recorded by that page's form (POST). Mail security gateways
    (Outlook Safe Links, Mimecast, Proofpoint, ...) fetch every link in a
    message to scan it -- a one-click GET that wrote the rating let a
    scanner visiting good -> okay -> bad leave "bad" as the customer's
    answer. Scanners don't submit forms, so only a real click-through can.
    """

    def _get_ticket(self, ticket_id, token, rating):
        """The ticket if ticket/token/rating all check out, else None.

        No record id from the URL is trusted without a check: the token is
        an hmac of ticket_id itself (helpdesk.ticket._get_rating_token), so
        a token can never be replayed against a different ticket_id.
        """
        ticket = request.env["helpdesk.ticket"].sudo().browse(ticket_id).exists()
        # pylint: disable=protected-access
        if (
            not ticket
            or rating not in VALID_RATINGS
            or not ticket._rating_token_is_valid(token)
        ):
            return None
        return ticket

    @http.route(
        ["/helpdesk/rate/<int:ticket_id>/<string:token>/<string:rating>"],
        type="http",
        auth="public",
        methods=["GET"],
        website=True,
    )
    def rate_ticket(self, ticket_id, token, rating, **kw):
        # pylint: disable=unused-argument
        # **kw absorbs stray query-string params so an unexpected one
        # doesn't turn into a TypeError on this public route.
        """Show the confirmation page for a rating link -- never writes."""
        ticket = self._get_ticket(ticket_id, token, rating)
        if not ticket:
            return request.render(PAGE, {"state": "invalid"})
        # pylint: disable=protected-access
        if ticket._rating_is_locked():
            return request.render(PAGE, {"state": "locked", "ticket": ticket})
        return request.render(
            PAGE,
            {
                "state": "confirm",
                "ticket": ticket,
                "token": token,
                "rating": rating,
                "rating_label": rating.capitalize(),
            },
        )

    # csrf=False: this route is anonymous and session-less -- the per-ticket
    # hmac in the URL *is* the credential. A CSRF token would protect
    # nothing extra: anyone able to forge this POST already holds the hmac,
    # and with it could simply submit the form themselves.
    @http.route(
        ["/helpdesk/rate/<int:ticket_id>/<string:token>/submit"],
        type="http",
        auth="public",
        methods=["POST"],
        website=True,
        csrf=False,
    )
    def rate_ticket_submit(self, ticket_id, token, rating=None, **kw):
        # pylint: disable=unused-argument
        """Re-validate everything and record the confirmed rating.

        Nothing from the GET page is trusted: the token, the rating value
        and the update window are all checked again here.
        """
        ticket = self._get_ticket(ticket_id, token, rating)
        if not ticket:
            return request.render(PAGE, {"state": "invalid"})
        # pylint: disable=protected-access
        if not ticket._apply_rating(rating):
            return request.render(PAGE, {"state": "locked", "ticket": ticket})
        return request.render(
            PAGE,
            {"state": "thanks", "ticket": ticket, "rating_label": rating.capitalize()},
        )
