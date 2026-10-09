TICKET_TYPES = ("incident", "request", "problem")
TICKET_STATUSES = ("new", "assigned", "in_progress", "pending", "resolved", "closed")
TICKET_PRIORITIES = ("low", "medium", "high", "critical")
TICKET_OPEN_STATUSES = ("new", "assigned", "in_progress", "pending")
TICKET_CLOSED_STATUSES = ("resolved", "closed")

STATUS_GLOSS = {
    "new": "we've just received it",
    "assigned": "a support person now owns it",
    "in_progress": "a support person is actively working on it",
    "pending": "we're waiting on something — check the ticket or your last email",
    "resolved": "we believe this is fixed — if it still isn't, say so and we'll reopen it",
    "closed": "this ticket is closed",
}