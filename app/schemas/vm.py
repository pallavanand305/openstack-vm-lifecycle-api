from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, Any, List
from enum import Enum
from datetime import datetime


class VMStatus(str, Enum):
    ACTIVE = "ACTIVE"
    STOPPED = "STOPPED"
    PAUSED = "PAUSED"
    SUSPENDED = "SUSPENDED"
    SHELVED = "SHELVED"
    SHELVED_OFFLOADED = "SHELVED_OFFLOADED"
    BUILD = "BUILD"
    REBUILD = "REBUILD"
    RESIZE = "RESIZE"
    ERROR = "ERROR"
    DELETED = "DELETED"
    UNKNOWN = "UNKNOWN"


class VMCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="VM display name")
    flavor_id: str = Field(..., description="OpenStack flavor ID or name")
    image_id: str = Field(..., description="OpenStack image ID or name")
    network_id: Optional[str] = Field(None, description="Network ID to attach. Uses default if omitted.")
    key_name: Optional[str] = Field(None, description="SSH keypair name")
    security_groups: Optional[List[str]] = Field(default_factory=list)
    user_data: Optional[str] = Field(None, description="Base64-encoded cloud-init script")
    metadata: Optional[Dict[str, str]] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def name_no_spaces(cls, v: str) -> str:
        # OpenStack allows spaces but it causes headaches — enforce clean names
        if v != v.strip():
            raise ValueError("VM name must not have leading or trailing whitespace")
        return v


class VMActionRequest(BaseModel):
    """Generic action payload — some actions need extra params (e.g. resize)."""
    action: str = Field(..., description="Action to perform: start | stop | reboot | pause | unpause | suspend | resume | shelve | unshelve")
    hard: Optional[bool] = Field(False, description="For reboot: hard reboot if true")
    flavor_id: Optional[str] = Field(None, description="For resize action: target flavor")


class VMResponse(BaseModel):
    id: str
    name: str
    status: VMStatus
    flavor: Dict[str, Any]
    image: Optional[Dict[str, Any]]
    addresses: Dict[str, Any]
    key_name: Optional[str]
    metadata: Dict[str, Any]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    host_id: Optional[str] = Field(None, description="Opaque host identifier")
    availability_zone: Optional[str]
    power_state: Optional[int]
    task_state: Optional[str]

    model_config = {"from_attributes": True}


class VMListResponse(BaseModel):
    items: List[VMResponse]
    total: int
    page: int
    page_size: int


class VMConsoleResponse(BaseModel):
    type: str
    url: str


class ErrorResponse(BaseModel):
    detail: str
    vm_id: Optional[str] = None
