"""Pure reference state for a future boot selector; no persistence or hardware I/O.

The user chooses a model. Display geometry, lid and stick metadata are derived
from the user-supplied catalog, not individually editable controls. A model name
does not certify a complete panel driver or physical acceptance.
"""
from dataclasses import dataclass, replace
from enum import Enum
from types import MappingProxyType
from typing import Mapping, Optional, Tuple


SCHEMA_VERSION = 2
DEFAULT_MODEL_ID = "rg34xxsp"


class Geometry(str, Enum):
    W720_H480 = "720x480"
    W640_H480 = "640x480"
    W720_H720 = "720x720"


class FormFactor(str, Enum):
    LANDSCAPE = "landscape"
    PORTRAIT = "portrait"
    CLAMSHELL = "clamshell"


@dataclass(frozen=True)
class ModelSpec:
    """Catalog metadata only; wifi=None means the user did not specify it."""

    model_id: str
    label: str
    geometry: Geometry
    form_factor: FormFactor
    sticks: int
    wifi: Optional[bool] = None
    aliases: Tuple[str, ...] = ()

    @property
    def lid(self):
        return self.form_factor is FormFactor.CLAMSHELL

    def to_mapping(self):
        """Export for preview/build tools; importing this module does no I/O."""
        return {"model_id": self.model_id, "label": self.label,
                "geometry": self.geometry.value, "form_factor": self.form_factor.value,
                "lid": self.lid, "sticks": self.sticks, "wifi": self.wifi,
                "aliases": list(self.aliases)}


# The user's supplied order. Original RGSP stays 720x480 and remains distinct
# from retail RG35XX SP. This catalog is the single source for model metadata.
MODEL_CATALOG: Tuple[ModelSpec, ...] = (
    ModelSpec("rg34xx", "34XX", Geometry.W720_H480, FormFactor.LANDSCAPE, 0),
    ModelSpec("rg34xxsp", "34XX SP", Geometry.W720_H480, FormFactor.CLAMSHELL, 2),
    ModelSpec("rgsp", "RGSP", Geometry.W720_H480, FormFactor.CLAMSHELL, 0),
    ModelSpec("rgcubexx", "CubeXX", Geometry.W720_H720, FormFactor.LANDSCAPE, 2),
    ModelSpec("rg35xxplus", "35XX Plus", Geometry.W640_H480, FormFactor.PORTRAIT, 0),
    ModelSpec("rg35xx_2025", "35XX+（2025）", Geometry.W640_H480,
              FormFactor.PORTRAIT, 0, False, ("35XX+", "35XX 2025", "35XX2025版")),
    ModelSpec("rg28xx", "28XX", Geometry.W640_H480, FormFactor.LANDSCAPE, 0, False),
    ModelSpec("rg35xxh", "35XX H", Geometry.W640_H480, FormFactor.LANDSCAPE, 2),
    ModelSpec("rg40xxh", "40XX H", Geometry.W640_H480, FormFactor.LANDSCAPE, 2),
    ModelSpec("rg40xxv", "40XX V", Geometry.W640_H480, FormFactor.PORTRAIT, 1),
    ModelSpec("rg35xxsp", "35XX SP", Geometry.W640_H480, FormFactor.CLAMSHELL, 0),
    ModelSpec("rg35xxpro", "35XX Pro", Geometry.W640_H480, FormFactor.PORTRAIT, 2),
)
_MODEL_BY_ID = MappingProxyType({model.model_id: model for model in MODEL_CATALOG})


class SupportStatus(str, Enum):
    UNVALIDATED = "unvalidated"
    UNSUPPORTED = "unsupported"
    VALIDATED = "validated"


class BootRoute(str, Enum):
    SHOW_SELECTOR = "show_selector"
    SKIP_SELECTOR = "skip_selector"


@dataclass(frozen=True)
class Selection:
    model_id: str = DEFAULT_MODEL_ID

    def __post_init__(self):
        if type(self.model_id) is not str or self.model_id not in _MODEL_BY_ID:
            raise ValueError("model_id must be a canonical catalog identifier")

    @property
    def model(self):
        return _MODEL_BY_ID[self.model_id]

    @property
    def geometry(self):
        return self.model.geometry

    @property
    def lid(self):
        return self.model.lid

    @property
    def sticks(self):
        return self.model.sticks


# Twelve model intents, not twelve accepted electrical/timing profiles.
CHOICES: Tuple[Selection, ...] = tuple(Selection(model.model_id) for model in MODEL_CATALOG)


@dataclass(frozen=True)
class PanelResolution:
    """External resolver result, bound to one model intent; never inferred by UI."""

    selection: Selection
    status: SupportStatus = SupportStatus.UNVALIDATED
    resolved_panel_id: Optional[str] = None
    detail: str = "A complete panel profile has not been resolved or validated."

    def __post_init__(self):
        if not isinstance(self.selection, Selection):
            raise ValueError("resolution must refer to a Selection")
        if not isinstance(self.status, SupportStatus):
            raise ValueError("status must be a declared SupportStatus")
        if type(self.detail) is not str:
            raise ValueError("detail must be text")
        if self.resolved_panel_id is not None:
            value = self.resolved_panel_id
            if type(value) is not str or not value or not value.isascii():
                raise ValueError("resolved_panel_id must be a nonempty ASCII identifier")
            if any(not (c.isalnum() or c in "._-") for c in value):
                raise ValueError("resolved_panel_id contains an invalid character")
        if self.status is SupportStatus.VALIDATED and self.resolved_panel_id is None:
            raise ValueError("validated requires an external complete panel identifier")
        if self.status is SupportStatus.UNSUPPORTED and self.resolved_panel_id is not None:
            raise ValueError("unsupported cannot resolve to a panel identifier")


@dataclass(frozen=True)
class ConfigIntent:
    """Schema v2 stores model preference only, not a bootable panel profile."""

    selection: Selection

    def __post_init__(self):
        if not isinstance(self.selection, Selection):
            raise ValueError("config must refer to a Selection")

    def to_mapping(self):
        return {"schema": SCHEMA_VERSION, "model_id": self.selection.model_id}

    @classmethod
    def from_mapping(cls, value: Mapping):
        if not isinstance(value, Mapping) or set(value) != {"schema", "model_id"}:
            raise ValueError("config keys must be exactly schema, model_id")
        if type(value["schema"]) is not int or value["schema"] != SCHEMA_VERSION:
            raise ValueError("unsupported schema; geometry/lid cannot identify a model")
        return cls(Selection(value["model_id"]))


@dataclass(frozen=True)
class StartIntent:
    """Returned only by explicit start confirmation; performs no actions.

    save_request is only a request to a future integration. Neither its presence
    nor confirmation certifies the panel or authorizes direct hardware writes.
    """

    resolution: PanelResolution
    save_request: Optional[ConfigIntent]


@dataclass(frozen=True)
class SelectorState:
    selection: Selection = Selection()
    save_default: bool = False

    def __post_init__(self):
        if not isinstance(self.selection, Selection):
            raise ValueError("state must refer to a Selection")
        if type(self.save_default) is not bool:
            raise ValueError("save_default must be a bool")

    def choose_model(self, model_id: str):
        return replace(self, selection=Selection(model_id))

    def cycle_model(self, direction: int):
        """One left/right press, wrapping at either end of the supplied list."""
        if type(direction) is not int or direction not in (-1, 1):
            raise ValueError("direction must be -1 (left) or 1 (right)")
        index = CHOICES.index(self.selection)
        return replace(self, selection=CHOICES[(index + direction) % len(CHOICES)])

    def choose_save_default(self, enabled: bool):
        return replace(self, save_default=enabled)

    def preview(self):
        # Catalog metadata does not supply a complete panel resolver.
        return PanelResolution(self.selection)

    def confirm_start(self, resolution: Optional[PanelResolution] = None):
        """Model one explicit user Start confirmation, not a focus/toggle event."""
        if resolution is None:
            resolution = self.preview()
        if not isinstance(resolution, PanelResolution) or resolution.selection != self.selection:
            raise ValueError("resolver result does not match current selection")
        request = ConfigIntent(self.selection) if self.save_default else None
        return StartIntent(resolution, request)

    @classmethod
    def from_config(cls, value: Mapping):
        # Explicitly opening the editor does not confirm Start or save again.
        return cls(ConfigIntent.from_mapping(value).selection, save_default=False)


@dataclass(frozen=True)
class StartupDecision:
    """Pure boot routing from an already-read saved model preference.

    SKIP_SELECTOR passes the saved intent to a future panel resolver. It does
    not resolve a panel, certify display readiness, execute Start, or save.
    """

    route: BootRoute
    state: SelectorState
    saved_intent: Optional[ConfigIntent] = None
    config_error: Optional[str] = None

    def __post_init__(self):
        if not isinstance(self.route, BootRoute) or not isinstance(self.state, SelectorState):
            raise ValueError("startup requires a declared route and selector state")
        if self.config_error is not None and type(self.config_error) is not str:
            raise ValueError("config_error must be text or None")
        if self.route is BootRoute.SKIP_SELECTOR:
            if (not isinstance(self.saved_intent, ConfigIntent)
                    or self.saved_intent.selection != self.state.selection
                    or self.state.save_default or self.config_error is not None):
                raise ValueError("skip requires the matching valid saved intent")
        elif self.saved_intent is not None:
            raise ValueError("menu route cannot carry a saved boot intent")

    @classmethod
    def from_saved_config(cls, value=None):
        """No/invalid record shows defaults; ambiguous old records are not guessed."""
        if value is None:
            return cls(BootRoute.SHOW_SELECTOR, SelectorState())
        try:
            intent = ConfigIntent.from_mapping(value)
        except ValueError as error:
            return cls(BootRoute.SHOW_SELECTOR, SelectorState(), config_error=str(error))
        state = SelectorState(intent.selection, save_default=False)
        return cls(BootRoute.SKIP_SELECTOR, state, saved_intent=intent)

    def preview(self):
        # Skipping a preference editor is independent of panel validation.
        return self.state.preview()
