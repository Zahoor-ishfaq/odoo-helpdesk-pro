"""Helpdesk ticket: a single customer support request."""

import hashlib
import hmac
import logging
from datetime import timedelta

# pylint: disable=import-error
# odoo is not installed in the isolated pylint-odoo pre-commit environment.
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import consteq
from odoo.tools.mail import email_split_tuples

_logger = logging.getLogger(__name__)

RATING_SELECTION = [
    ("good", "Good"),
    ("okay", "Okay"),
    ("bad", "Bad"),
]
RATING_WINDOW_DAYS = 7

HELPDESK_PRIORITY_SELECTION = [
    ("0", "Low"),
    ("1", "Medium"),
    ("2", "High"),
    ("3", "Urgent"),
]


class HelpdeskTicket(models.Model):  # pylint: disable=too-few-public-methods
    """A customer support ticket moving through a team's stage pipeline."""

    _name = "helpdesk.ticket"
    _description = "Helpdesk Ticket"
    _inherit = ["mail.thread", "mail.activity.mixin", "portal.mixin"]
    _order = "priority desc, id desc"
    # Portal customers only have read access (ir.model.access.csv), but must
    # still be able to reply from the portal chatter -- without this, mail's
    # default _mail_post_access="write" silently blocks their composer (same
    # pattern as project.task, which portal users also comment on).
    _mail_post_access = "read"

    name = fields.Char(string="Subject", required=True, tracking=True)
    ref = fields.Char(default="New", readonly=True, copy=False)
    team_id = fields.Many2one("helpdesk.team", required=True, index=True, tracking=True)
    stage_id = fields.Many2one(
        "helpdesk.stage",
        required=True,
        index=True,
        tracking=True,
        # pylint: disable=protected-access
        default=lambda self: self._default_stage_id(),
        group_expand="_read_group_stage_ids",
    )
    user_id = fields.Many2one(
        "res.users",
        string="Assigned to",
        index=True,
        tracking=True,
        domain=[("share", "=", False)],
    )
    partner_id = fields.Many2one(
        "res.partner", string="Customer", index=True, tracking=True
    )
    partner_email = fields.Char(string="Customer Email")
    partner_name = fields.Char(string="Customer Name")
    priority = fields.Selection(HELPDESK_PRIORITY_SELECTION, default="1", required=True)
    tag_ids = fields.Many2many("helpdesk.tag", string="Tags")
    description = fields.Html()
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company
    )
    color = fields.Integer(string="Color Index", default=0)
    active = fields.Boolean(default=True)

    sla_id = fields.Many2one(
        "helpdesk.sla",
        string="SLA Policy",
        compute="_compute_sla_id",
        store=True,
        help="Most specific active policy matching this ticket's team, "
        "priority and tags.",
    )
    sla_deadline = fields.Datetime(
        compute="_compute_sla_deadline",
        store=True,
        index=True,
        help="Working-hours deadline from the matched SLA policy. Frozen "
        "once the ticket reaches a closed stage.",
    )
    sla_status = fields.Selection(
        [
            ("ok", "On Track"),
            ("at_risk", "At Risk"),
            ("breached", "Breached"),
        ],
        compute="_compute_sla_status",
        store=True,
        help="Frozen once the ticket reaches a closed stage.",
    )
    sla_reached = fields.Boolean(
        default=False,
        copy=False,
        help="Set when the ticket entered a closed stage before its SLA " "deadline.",
    )

    rating = fields.Selection(
        RATING_SELECTION, copy=False, help="Empty until the customer rates the ticket."
    )
    rating_token = fields.Char(
        copy=False, help="Signed token embedded in the CSAT email's rating links."
    )
    rating_date = fields.Datetime(copy=False)

    assign_date = fields.Datetime(
        copy=False, help="Set the first time the ticket is assigned to an agent."
    )
    close_date = fields.Datetime(
        copy=False,
        help="Set each time the ticket enters a closed stage; cleared when it "
        "is reopened.",
    )
    open_hours = fields.Float(
        compute="_compute_open_hours",
        store=True,
        help="Calendar-aware working hours elapsed since creation. Frozen "
        "once the ticket reaches a closed stage.",
    )
    resolution_hours = fields.Float(
        compute="_compute_resolution_hours",
        store=True,
        help="Calendar-aware working hours from creation to close_date. "
        "Zero while the ticket has never been closed.",
    )

    @api.model
    def _default_stage_id(self):
        """First stage of the context's team (form views opened from a
        team), or the first shared stage when there's no team yet."""
        team = self.env["helpdesk.team"].browse(self.env.context.get("default_team_id"))
        # pylint: disable=protected-access
        return self.env["helpdesk.stage"]._get_team_first_stage(team)

    @api.model
    # PORT-19: group_expand callables are invoked with 2 args (records,
    # domain), not 3 (records, domain, order) as on 17.0 -- order is no
    # longer passed, so this relies on helpdesk.stage's own _order.
    def _read_group_stage_ids(self, stages, _domain):
        """All stages as kanban columns -- only the team's own and shared
        ones when opened from a team (action_view_tickets)."""
        team_id = self.env.context.get("default_team_id")
        if not team_id:
            return stages.search([])
        team = self.env["helpdesk.team"].browse(team_id)
        # pylint: disable=protected-access
        return stages.search(stages._get_team_stages_domain(team))

    @api.constrains("stage_id", "team_id")
    def _check_stage_team(self):
        """Keep imports/RPC from putting a ticket in another team's stage --
        the form's stage domain only guards the UI."""
        stage_model = self.env["helpdesk.stage"]
        for ticket in self:
            # pylint: disable=protected-access
            domain = stage_model._get_team_stages_domain(ticket.team_id)
            if not ticket.stage_id.filtered_domain(domain):
                raise ValidationError(
                    _(
                        "Stage %(stage)s is not available for team %(team)s.",
                        stage=ticket.stage_id.name,
                        team=ticket.team_id.name,
                    )
                )

    def _get_team_stage_for(self, team):
        """Where this ticket should land on moving to `team`: its current
        stage if the team can use it, else the team's first stage with the
        same open/closed state, else simply the team's first stage."""
        self.ensure_one()
        stage_model = self.env["helpdesk.stage"]
        # pylint: disable=protected-access
        if self.stage_id.filtered_domain(stage_model._get_team_stages_domain(team)):
            return self.stage_id
        return stage_model._get_team_first_stage(
            team, is_closed=self.stage_id.is_closed
        ) or stage_model._get_team_first_stage(team)

    @api.onchange("team_id")
    def _onchange_team_id(self):
        """Form-side twin of the team-change handling in write().

        On a not-yet-saved ticket the stage is only the field default, so it
        follows the team's first stage outright, as create() would.
        """
        stage_model = self.env["helpdesk.stage"]
        # pylint: disable=protected-access
        for ticket in self:
            if not ticket.team_id:
                continue
            if not ticket._origin:
                ticket.stage_id = stage_model._get_team_first_stage(ticket.team_id)
            else:
                ticket.stage_id = ticket._get_team_stage_for(ticket.team_id)

    def _compute_access_url(self):
        super()._compute_access_url()
        for ticket in self:
            ticket.access_url = f"/my/ticket/{ticket.id}"

    @api.depends("team_id", "priority", "tag_ids")
    def _compute_sla_id(self):
        for ticket in self:
            # pylint: disable=protected-access
            ticket.sla_id = self.env["helpdesk.sla"]._search_best_match(
                ticket.team_id, ticket.priority, ticket.tag_ids
            )

    @api.depends("sla_id", "team_id", "create_date")
    def _compute_sla_deadline(self):
        for ticket in self:
            if ticket.stage_id.is_closed:
                ticket.sla_deadline = ticket.sla_deadline  # frozen, no-op
                continue
            if not ticket.sla_id or not ticket.team_id.calendar_id:
                ticket.sla_deadline = False
                continue
            start = ticket.create_date or fields.Datetime.now()
            calendar = ticket.team_id.calendar_id
            deadline = calendar.plan_hours(
                ticket.sla_id.target_hours, start, compute_leaves=True
            )
            if not deadline:
                # plan_hours() returns False when the calendar can't fit the
                # hours at all (e.g. no attendances). That's a configuration
                # problem for the admin, not a reason to fail ticket
                # creation or the SLA cron -- leave the ticket without a
                # deadline and say why.
                _logger.warning(
                    "helpdesk: SLA policy %r matched ticket %s but calendar "
                    "%r of team %r yields no deadline; check its working hours",
                    ticket.sla_id.name,
                    ticket.id,
                    calendar.name,
                    ticket.team_id.name,
                )
            ticket.sla_deadline = deadline or False

    @api.depends("sla_deadline", "sla_id.target_hours")
    def _compute_sla_status(self):
        now = fields.Datetime.now()
        for ticket in self:
            if ticket.stage_id.is_closed:
                ticket.sla_status = ticket.sla_status  # frozen, no-op
                continue
            # No deadline despite a policy: the calendar couldn't place one
            # (see _compute_sla_deadline) -- no status rather than a crash.
            if not ticket.sla_id or not ticket.sla_deadline:
                ticket.sla_status = False
                continue
            remaining = (ticket.sla_deadline - now).total_seconds()
            if remaining <= 0:
                ticket.sla_status = "breached"
            elif remaining < 0.25 * (ticket.sla_id.target_hours * 3600):
                ticket.sla_status = "at_risk"
            else:
                ticket.sla_status = "ok"

    @api.model
    def _cron_update_sla_status(self):
        """Batch-refresh sla_status for open tickets (data/helpdesk_cron.xml).

        The @api.depends compute keeps sla_status correct the instant a
        relevant field changes, but elapsed time alone never triggers it --
        only this periodic pass catches a deadline quietly slipping into
        at_risk/breached with no field having changed.
        """
        tickets = self.search(
            [("sla_deadline", "!=", False), ("stage_id.is_closed", "=", False)]
        )
        tickets._compute_sla_status()  # pylint: disable=protected-access

    @api.depends("create_date")
    def _compute_open_hours(self):
        now = fields.Datetime.now()
        for ticket in self:
            if ticket.stage_id.is_closed:
                ticket.open_hours = ticket.open_hours  # frozen, no-op
                continue
            if not ticket.create_date or not ticket.team_id.calendar_id:
                ticket.open_hours = 0.0
                continue
            duration = ticket.team_id.calendar_id.get_work_duration_data(
                ticket.create_date, now, compute_leaves=True
            )
            ticket.open_hours = duration["hours"]

    @api.depends("close_date")
    def _compute_resolution_hours(self):
        for ticket in self:
            if (
                not ticket.close_date
                or not ticket.create_date
                or not ticket.team_id.calendar_id
            ):
                ticket.resolution_hours = 0.0
                continue
            duration = ticket.team_id.calendar_id.get_work_duration_data(
                ticket.create_date, ticket.close_date, compute_leaves=True
            )
            ticket.resolution_hours = duration["hours"]

    @api.model
    def _cron_update_open_hours(self):
        """Batch-refresh open_hours for all open tickets (data/helpdesk_cron.xml).

        Broader domain than _cron_update_sla_status on purpose: a ticket
        with no matching SLA policy still has an age worth tracking for
        analytics, it just has no deadline to breach.
        """
        tickets = self.search([("stage_id.is_closed", "=", False)])
        tickets._compute_open_hours()  # pylint: disable=protected-access

    @api.model_create_multi
    def create(self, vals_list):
        """Default each ticket's stage from its team, and assign the next
        TKT/YYYY/NNNNN sequence value to new tickets."""
        stage_model = self.env["helpdesk.stage"]
        for vals in vals_list:
            # The field default only sees the context's default_team_id,
            # not the team_id in vals, so resolve per ticket here.
            if not vals.get("stage_id") and vals.get("team_id"):
                team = self.env["helpdesk.team"].browse(vals["team_id"])
                # pylint: disable=protected-access
                stage = stage_model._get_team_first_stage(team)
                if stage:
                    vals["stage_id"] = stage.id
            if vals.get("ref", "New") == "New":
                vals["ref"] = (
                    self.env["ir.sequence"].next_by_code("helpdesk.ticket") or "New"
                )
        tickets = super().create(vals_list)
        # Force the SLA chain to compute and flush now, while the ticket is
        # still in its just-created (open) stage. Left pending, these
        # stored fields stay "to-compute" past this method returning --
        # whatever next triggers a flush (e.g. a later write closing the
        # ticket) would recompute them then, and the closed-stage freeze
        # guard in _compute_sla_deadline/_compute_sla_status would see its
        # own field still mid-computation and freeze it at the empty
        # default instead of the real value it should have captured while
        # still open.
        tickets.flush_recordset(
            ["sla_id", "sla_deadline", "sla_status", "open_hours", "resolution_hours"]
        )
        return tickets

    def write(self, vals):
        """Set sla_reached/close_date/CSAT request on each transition into a
        closed stage, clear them again on a transition back out of one
        (reopen), and set assign_date on first assignment.

        sla_deadline/sla_status are frozen simply by not depending on
        stage_id -- this write is only about capturing point-in-time facts
        (transitions) that a depends-based compute can't see, it only sees
        resulting states.

        A reopen doesn't grant a fresh SLA: the deadline stays anchored to
        create_date, since the customer's original request is still the one
        waiting. A re-close then evaluates sla_reached against it again.

        Also posts the new stage's mail_template_id (if any) into the
        chatter of every ticket whose stage actually changes.

        context key `skip_csat_email`: used by the merge wizard when it
        closes the source ticket -- that closure isn't a real resolution,
        so it shouldn't survey the customer.

        context key `skip_stage_email`: same idea for the stage template --
        the merge wizard's close isn't a stage transition the customer
        should hear about.

        Changing team_id without a stage_id moves any ticket whose stage the
        new team can't use to a stage it can (see _get_team_stage_for),
        going through this same write so the usual transition side effects
        still apply.
        """
        if vals.get("team_id") and not vals.get("stage_id"):
            team = self.env["helpdesk.team"].browse(vals["team_id"])
            # pylint: disable=protected-access
            moving = self.filtered(lambda t: t._get_team_stage_for(team) != t.stage_id)
            for ticket in moving:
                stage = ticket._get_team_stage_for(team)
                ticket.write(dict(vals, stage_id=stage.id))
            if moving:
                rest = self - moving
                return rest.write(vals) if rest else True
        newly_closing = self.browse()
        newly_reopening = self.browse()
        stage_changing = self.browse()
        if vals.get("stage_id"):
            new_stage = self.env["helpdesk.stage"].browse(vals["stage_id"])
            stage_changing = self.filtered(lambda t: t.stage_id != new_stage)
            if new_stage.is_closed:
                newly_closing = self.filtered(lambda t: not t.stage_id.is_closed)
            else:
                newly_reopening = self.filtered(lambda t: t.stage_id.is_closed)

        newly_assigned = self.browse()
        if vals.get("user_id"):
            newly_assigned = self.filtered(
                lambda t: not t.user_id and not t.assign_date
            )

        result = super().write(vals)

        if newly_assigned:
            newly_assigned.assign_date = fields.Datetime.now()

        # pylint: disable=protected-access
        if newly_reopening:
            newly_reopening._on_reopen()

        # Before the CSAT email below, so a customer whose ticket closes
        # into a stage with a template reads "resolved" before "rate us".
        if stage_changing and not self.env.context.get("skip_stage_email"):
            stage_changing._send_stage_email()

        if newly_closing:
            newly_closing._on_close()
        return result

    def _on_close(self):
        """Record the point-in-time close facts and survey the customer."""
        now = fields.Datetime.now()
        for ticket in self:
            if ticket.sla_id and ticket.sla_deadline:
                ticket.sla_reached = now <= ticket.sla_deadline
            ticket.close_date = now
            if ticket.team_id.csat_enabled and not self.env.context.get(
                "skip_csat_email"
            ):
                # pylint: disable=protected-access
                ticket.rating_token = ticket._get_rating_token()
                ticket._send_rating_email()

    def _on_reopen(self):
        """Undo the close facts and bring the frozen SLA fields up to date."""
        # resolution_hours follows close_date back to 0 on its own.
        self.write({"close_date": False, "sla_reached": False})
        # The SLA fields were frozen while closed and none of them depends
        # on stage_id, so nothing would recompute them until the next cron
        # pass -- until then the ticket would show its stale at-close
        # status. Call the computes directly, exactly as the crons do: the
        # stage is open again by now (write() calls this after super()),
        # so the freeze guards let them through, and nothing is left
        # pending for a later flush to freeze at the wrong value (see the
        # comment in create()).
        self._compute_sla_deadline()
        self._compute_sla_status()
        self._compute_open_hours()

    @api.model
    def message_new(self, msg_dict, custom_values=None):
        """Create a ticket from an inbound email (see mail.thread).

        team_id comes from the alias's own defaults (helpdesk.team's
        _alias_get_creation_values), not from anything parsed here.
        """
        defaults = dict(custom_values or {})
        defaults.setdefault("name", msg_dict.get("subject") or _("No Subject"))
        defaults.setdefault("description", msg_dict.get("body"))
        # pylint: disable=broad-except
        # Inbound mail must never crash the gateway: any unexpected shape
        # here (missing/garbled headers) falls back to a bare ticket.
        try:
            email_from = msg_dict.get("email_from") or ""
            pairs = email_split_tuples(email_from)
            name, email = pairs[0] if pairs else ("", email_from)
            defaults.setdefault("partner_email", email)
            defaults.setdefault("partner_name", name or email)
            if msg_dict.get("author_id"):
                defaults.setdefault("partner_id", msg_dict["author_id"])
        except Exception:
            _logger.warning(
                "helpdesk: could not parse sender %r on inbound email %r, "
                "falling back to a bare ticket",
                msg_dict.get("email_from"),
                msg_dict.get("message_id"),
                exc_info=True,
            )
        ticket = super().message_new(msg_dict, custom_values=defaults)
        ticket._send_ack_email()  # pylint: disable=protected-access
        return ticket

    def message_update(self, msg_dict, update_vals=None):
        """Reopen a closed ticket when the customer replies (see mail.thread),
        into the first open stage of the ticket's own team.

        Threading the reply into the chatter itself is already handled by
        the mail gateway (message_post, called separately by
        _message_route_process) -- this only needs the reopen side effect.
        """
        stage_model = self.env["helpdesk.stage"]
        for ticket in self:
            if not ticket.stage_id.is_closed:
                continue
            # pylint: disable=protected-access
            open_stage = stage_model._get_team_first_stage(
                ticket.team_id, is_closed=False
            )
            if open_stage:
                ticket.stage_id = open_stage
        return super().message_update(msg_dict, update_vals=update_vals)

    def _send_ack_email(self):
        """Queue the "ticket received" acknowledgement for email-created tickets."""
        self.ensure_one()
        if not self.partner_email:
            return
        template = self.env.ref(
            "helpdesk_community_pro.mail_template_ticket_received",
            raise_if_not_found=False,
        )
        if template:
            template.send_mail(self.id, force_send=False)

    def _send_stage_email(self):
        """Post each ticket's (new) stage template into its chatter.

        message_post_with_source rather than template.send_mail: the email
        then shows up in the ticket's history like any other reply, instead
        of leaving no trace on the ticket. Tickets with nobody to write to
        are skipped rather than posting a message that reaches no one.
        """
        for ticket in self:
            template = ticket.stage_id.mail_template_id
            if not template or not (ticket.partner_id or ticket.partner_email):
                continue
            ticket.message_post_with_source(template, subtype_xmlid="mail.mt_comment")

    def _get_rating_token(self):
        """Deterministic signature for this ticket's public rating links.

        hmac(db secret, ticket id) rather than a stored random value: the
        public rating controller re-derives the same signature from the
        URL's ticket_id and compares, so a token can never be replayed
        against a different ticket_id. Still stored on the field (set once,
        on close) purely so the mail template can render object.rating_token
        directly without calling into Python.
        """
        self.ensure_one()
        secret = self.env["ir.config_parameter"].sudo().get_param("database.secret")
        payload = f"helpdesk.ticket-rating-{self.id}".encode()
        return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

    def _rating_token_is_valid(self, token):
        self.ensure_one()
        return bool(token) and consteq(token, self._get_rating_token())

    def _rating_is_locked(self):
        """Whether the RATING_WINDOW_DAYS update window has closed.

        Read-only on purpose: the public GET confirmation page needs to show
        the "locked" state without writing anything, and _apply_rating()
        reuses it so the window rule lives in exactly one place.
        """
        self.ensure_one()
        return bool(self.rating_date) and fields.Datetime.now() > (
            self.rating_date + timedelta(days=RATING_WINDOW_DAYS)
        )

    def _apply_rating(self, rating):
        """Record a customer's confirmed CSAT choice; returns False if the
        window has closed.

        First rating sets rating + rating_date. Further ratings update the
        value as long as they land within RATING_WINDOW_DAYS of that
        *first* rating_date (rating_date itself never moves, so the window
        doesn't reset/slide with each change) -- past it, the rating is
        locked and this returns False without writing anything.
        """
        self.ensure_one()
        if self._rating_is_locked():
            return False
        vals = {"rating": rating}
        if not self.rating_date:
            vals["rating_date"] = fields.Datetime.now()
        self.write(vals)
        return True

    def _send_rating_email(self):
        """Queue the CSAT "how did we do" email for a just-closed ticket."""
        self.ensure_one()
        if not self.partner_email:
            return
        template = self.env.ref(
            "helpdesk_community_pro.mail_template_ticket_rating",
            raise_if_not_found=False,
        )
        if template:
            template.send_mail(self.id, force_send=False)
