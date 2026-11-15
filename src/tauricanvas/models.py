import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Diagnostic(BaseModel):
    code: str
    severity: Literal['info', 'warning', 'error', 'fatal']
    stage: str
    message: str
    file: str | None = None
    line: int | None = None
    suggestion: str | None = None


class Parameter(BaseModel):
    name: str
    type_syntax: str
    borrowed: bool = False


class Function(BaseModel):
    identity: str
    package: str
    module: str
    name: str
    file: str
    line: int
    public: bool = False
    async_: bool = False
    unsafe: bool = False
    generic: bool = False
    parameters: list[Parameter] = Field(default_factory=list)
    return_type: str = '()'
    attributes: list[str] = Field(default_factory=list)
    classification: str = 'internal_not_candidate'
    reasons: list[str] = Field(default_factory=list)


class RustType(BaseModel):
    identity: str
    package: str
    name: str
    kind: str
    file: str
    line: int
    public: bool = False
    fields: list[Parameter] = Field(default_factory=list)


class Inspection(BaseModel):
    schema_version: int = 1
    manifest: str
    workspace_root: str
    packages: list[dict] = Field(default_factory=list)
    functions: list[Function] = Field(default_factory=list)
    types: list[RustType] = Field(default_factory=list)
    diagnostics: list[Diagnostic] = Field(default_factory=list)


class ProjectCfg(BaseModel):
    name: str
    identifier: str
    version: str = '0.1.0'
    description: str = ''


class SourceCfg(BaseModel):
    manifest: str
    package: str | None = None


class EngineCfg(BaseModel):
    mode: Literal['copy', 'link'] = 'copy'
    target: str = 'crates/app-engine'


class ActionSource(BaseModel):
    crate: str
    function: str


class Presentation(BaseModel):
    input: str = 'none'
    output: str = 'details'
    route: str | None = None


class ActionCfg(BaseModel):
    id: str
    enabled: bool = False
    source: ActionSource
    title: str
    safety: Literal['read_only', 'write', 'destructive', 'process'] = 'read_only'
    confirmation: bool = False
    presentation: Presentation = Field(default_factory=Presentation)

    @field_validator('id')
    @classmethod
    def valid_id(cls, v):
        if not re.fullmatch(r'[a-z][a-z0-9_]*', v):
            raise ValueError('id must be lower_snake_case starting with a letter')
        return v



class UiCfg(BaseModel):
    menus: bool = True
    theme_toggle: bool = True

class Config(BaseModel):
    model_config = ConfigDict(extra='forbid')
    schema_version: int = 1
    project: ProjectCfg
    source: SourceCfg
    engine: EngineCfg = Field(default_factory=EngineCfg)
    ui: UiCfg = Field(default_factory=UiCfg)
    actions: list[ActionCfg] = Field(default_factory=list)


class TypeRef(BaseModel):
    kind: str
    name: str | None = None
    item: Any | None = None
    optional: bool = False


class ActionContract(BaseModel):
    id: str
    title: str
    command: str
    source: str
    safety: str
    parameters: list[dict] = Field(default_factory=list)
    output: dict
    route: str | None = None
    async_: bool = True
    returns_result: bool = True


class Contract(BaseModel):
    schema_version: int = 1
    name: str
    identifier: str
    actions: list[ActionContract] = Field(default_factory=list)
