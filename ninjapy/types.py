from typing import TypedDict, List, Optional, Literal, Dict, Any

class CustomFieldCondition(TypedDict):
    fieldName: str
    operator: Literal["EQUALS", "NOT_EQUALS", "LESS_THAN", "LESS_OR_EQUAL_THAN",
                     "GREATER_THAN", "GREATER_OR_EQUAL_THAN", "IS_NOT_NULL",
                     "CONTAINS", "CONTAINS_NONE", "CONTAINS_ANY"]
    value: str

class PolicyConditionScript(TypedDict):
    scriptId: int
    runAs: Literal["SYSTEM", "LOGGED_ON_USER", "LOCAL_ADMIN", "DOMAIN_ADMIN",
                   "PREFERRED_CREDENTIAL_MAC", "PREFERRED_CREDENTIAL_LINUX"]
    scriptParam: Optional[str]
    scriptVariables: List[dict] 

class Organization(TypedDict):
    id: int
    name: str
    description: Optional[str]
    nodeApprovalMode: Optional[str]
    tags: Optional[List[str]]
    fields: Optional[Dict[str, Any]]

class Device(TypedDict):
    id: int
    organizationId: int
    locationId: Optional[int]
    nodeClass: str
    nodeRoleId: Optional[int]
    policyId: Optional[int]
    approvalStatus: str
    offline: bool
    displayName: str
    systemName: str
    created: float
    lastContact: float
    lastUpdate: float

class NotificationChannel(TypedDict):
    id: int
    name: str
    description: Optional[str]
    enabled: bool
    type: str 