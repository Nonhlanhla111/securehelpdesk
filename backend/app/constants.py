"""Fixed vocabularies: roles, categories, priorities, statuses and the ticket workflow."""
from enum import Enum


class RoleName(str, Enum):
    EMPLOYEE = "Employee"
    AGENT = "IT Support Agent"
    ADMIN = "Administrator"


class CategoryName(str, Enum):
    HARDWARE = "Hardware"
    SOFTWARE = "Software"
    NETWORK = "Network"
    ACCOUNT_ACCESS = "Account Access"
    SECURITY = "Security"
    EMAIL = "Email"
    SYSTEM_ISSUES = "System Issues"
    OTHER = "Other"


class PriorityName(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


class StatusName(str, Enum):
    OPEN = "Open"
    ASSIGNED = "Assigned"
    IN_PROGRESS = "In Progress"
    RESOLVED = "Resolved"
    CLOSED = "Closed"


class Severity(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


STAFF_ROLES = (RoleName.AGENT.value, RoleName.ADMIN.value)

# Workflow: Open -> Assigned -> In Progress -> Resolved -> Closed
# (Open -> Assigned happens through the /assign endpoint, not a plain status change.)
S = StatusName
STAFF_TRANSITIONS: dict[str, set[str]] = {
    S.ASSIGNED.value: {S.IN_PROGRESS.value},
    S.IN_PROGRESS.value: {S.RESOLVED.value},
    S.RESOLVED.value: {S.CLOSED.value, S.IN_PROGRESS.value},
}
# Employees may only confirm a resolution (close) or reject it (back to In Progress).
EMPLOYEE_TRANSITIONS: dict[str, set[str]] = {
    S.RESOLVED.value: {S.CLOSED.value, S.IN_PROGRESS.value},
}
