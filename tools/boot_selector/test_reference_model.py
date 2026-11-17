"""Reviewable host-model tests; no hardware or file operations."""
from dataclasses import FrozenInstanceError
import unittest

try:
    from .reference_model import (CHOICES, MODEL_CATALOG, BootRoute, ConfigIntent,
                                  FormFactor, Geometry, PanelResolution, Selection,
                                  SelectorState, StartupDecision, SupportStatus)
except ImportError:
    from reference_model import (CHOICES, MODEL_CATALOG, BootRoute, ConfigIntent,
                                 FormFactor, Geometry, PanelResolution, Selection,
                                 SelectorState, StartupDecision, SupportStatus)


class SelectorModelTests(unittest.TestCase):
    def test_exact_user_catalog_order_and_metadata(self):
        expected = (
            ("rg34xx", "720x480", "landscape", 0, None),
            ("rg34xxsp", "720x480", "clamshell", 2, None),
            ("rgsp", "720x480", "clamshell", 0, None),
            ("rgcubexx", "720x720", "landscape", 2, None),
            ("rg35xxplus", "640x480", "portrait", 0, None),
            ("rg35xx_2025", "640x480", "portrait", 0, False),
            ("rg28xx", "640x480", "landscape", 0, False),
            ("rg35xxh", "640x480", "landscape", 2, None),
            ("rg40xxh", "640x480", "landscape", 2, None),
            ("rg40xxv", "640x480", "portrait", 1, None),
            ("rg35xxsp", "640x480", "clamshell", 0, None),
            ("rg35xxpro", "640x480", "portrait", 2, None),
        )
        actual = tuple((m.model_id, m.geometry.value, m.form_factor.value, m.sticks, m.wifi)
                       for m in MODEL_CATALOG)
        self.assertEqual(actual, expected)
        self.assertEqual(len(set(CHOICES)), 12)
        self.assertEqual({m.model_id for m in MODEL_CATALOG if m.lid},
                         {"rg34xxsp", "rgsp", "rg35xxsp"})
        self.assertEqual(Selection("rgsp").geometry, Geometry.W720_H480)
        self.assertEqual(Selection("rg35xxsp").geometry, Geometry.W640_H480)
        self.assertEqual(Selection("rg35xxplus").model.label, "35XX Plus")
        self.assertEqual(Selection("rg35xx_2025").model.label, "35XX+（2025）")
        self.assertIn("35XX+", Selection("rg35xx_2025").model.aliases)

    def test_properties_are_derived_and_cannot_be_independently_changed(self):
        selection = Selection("rg34xxsp")
        self.assertTrue(selection.lid)
        self.assertEqual(selection.sticks, 2)
        self.assertEqual(selection.model.form_factor, FormFactor.CLAMSHELL)
        for field, value in (("geometry", Geometry.W640_H480), ("lid", False), ("sticks", 0)):
            with self.subTest(field=field), self.assertRaises(FrozenInstanceError):
                setattr(selection, field, value)
        with self.assertRaises(FrozenInstanceError):
            selection.model.label = "changed"
        self.assertFalse(hasattr(SelectorState(), "choose_geometry"))
        self.assertFalse(hasattr(SelectorState(), "choose_lid"))

    def test_left_right_cycle_wraps_and_preserves_save(self):
        first = SelectorState(CHOICES[0], save_default=True)
        self.assertEqual(first.cycle_model(-1).selection, CHOICES[-1])
        state = first
        for selection in CHOICES[1:] + CHOICES[:1]:
            state = state.cycle_model(1)
            self.assertEqual(state.selection, selection)
            self.assertTrue(state.save_default)
        self.assertEqual(state, first)
        for bad in (True, 0, 2, -2, "right"):
            with self.subTest(direction=bad), self.assertRaises(ValueError):
                first.cycle_model(bad)

    def test_catalog_does_not_claim_all_twelve_panels_supported(self):
        for selection in CHOICES:
            preview = SelectorState(selection).preview()
            self.assertEqual(preview.status, SupportStatus.UNVALIDATED)
            self.assertIsNone(preview.resolved_panel_id)

    def test_default_and_opt_in_save_only_at_start_confirmation(self):
        state = SelectorState()
        self.assertEqual(state.selection, Selection("rg34xxsp"))
        self.assertEqual(state.selection.geometry, Geometry.W720_H480)
        self.assertTrue(state.selection.lid)
        self.assertFalse(state.save_default)
        self.assertIsNone(state.confirm_start().save_request)
        enabled = state.choose_save_default(True).choose_model("rg35xxh")
        self.assertFalse(hasattr(enabled.preview(), "save_request"))
        self.assertEqual(enabled.confirm_start().save_request.to_mapping(),
                         {"schema": 2, "model_id": "rg35xxh"})
        self.assertIsNone(enabled.confirm_start().resolution.resolved_panel_id)

    def test_bad_model_ids_and_config_types_are_rejected(self):
        good = {"schema": 2, "model_id": "rg35xxh"}
        for bad in ({**good, "schema": True}, {**good, "schema": 1},
                    {**good, "schema": 3}, {**good, "model_id": 0},
                    {**good, "model_id": []}, {**good, "model_id": "35XX H"},
                    {**good, "model_id": "not-a-model"},
                    {**good, "geometry": "640x480"}, {**good, "lid": False},
                    {**good, "resolved_panel_id": "made-up"},
                    {**good, "save_default": True}):
            with self.subTest(value=bad), self.assertRaises(ValueError):
                ConfigIntent.from_mapping(bad)

    def test_ambiguous_old_geometry_lid_requires_model_selection(self):
        for geometry in Geometry:
            for lid in (False, True):
                old = {"schema": 1, "geometry": geometry.value, "lid": lid}
                with self.subTest(old=old):
                    with self.assertRaises(ValueError):
                        ConfigIntent.from_mapping(old)
                    decision = StartupDecision.from_saved_config(old)
                    self.assertEqual(decision.route, BootRoute.SHOW_SELECTOR)
                    self.assertEqual(decision.state, SelectorState())
                    self.assertTrue(decision.config_error)

    def test_loading_model_preference_does_not_request_save(self):
        value = {"schema": 2, "model_id": "rgcubexx"}
        state = SelectorState.from_config(value)
        self.assertEqual(ConfigIntent(state.selection).to_mapping(), value)
        self.assertFalse(state.save_default)
        self.assertIsNone(state.confirm_start().save_request)

    def test_every_saved_model_skips_without_claiming_panel_ready(self):
        for selection in CHOICES:
            with self.subTest(model=selection.model_id):
                request = SelectorState(selection, save_default=True).confirm_start().save_request
                decision = StartupDecision.from_saved_config(request.to_mapping())
                self.assertEqual(decision.route, BootRoute.SKIP_SELECTOR)
                self.assertEqual(decision.saved_intent, request)
                self.assertEqual(decision.state.selection, selection)
                self.assertFalse(decision.state.save_default)
                self.assertIsNone(decision.config_error)
                self.assertEqual(decision.preview().status, SupportStatus.UNVALIDATED)
                self.assertIsNone(decision.preview().resolved_panel_id)

    def test_no_or_invalid_record_shows_default_selector(self):
        decision = StartupDecision.from_saved_config()
        self.assertEqual(decision.route, BootRoute.SHOW_SELECTOR)
        self.assertEqual(decision.state, SelectorState())
        self.assertIsNone(decision.saved_intent)
        self.assertIsNone(decision.config_error)
        for bad in ({}, "not decoded config", {"schema": 2, "model_id": None}):
            with self.subTest(value=bad):
                decision = StartupDecision.from_saved_config(bad)
                self.assertEqual(decision.route, BootRoute.SHOW_SELECTOR)
                self.assertEqual(decision.state, SelectorState())
                self.assertIsNone(decision.saved_intent)
                self.assertTrue(decision.config_error)

    def test_resolver_cannot_follow_same_geometry_different_model(self):
        before = SelectorState().choose_model("rg35xxh")
        candidate = PanelResolution(before.selection, resolved_panel_id="candidate-only")
        for next_model in ("rg40xxh", "rg35xxsp"):
            after = before.choose_model(next_model)
            self.assertEqual(after.selection.geometry, before.selection.geometry)
            with self.subTest(model=next_model), self.assertRaises(ValueError):
                after.confirm_start(candidate)

    def test_unsupported_and_validated_are_external_explicit_results(self):
        selection = Selection("rgcubexx")
        unsupported = PanelResolution(selection, SupportStatus.UNSUPPORTED,
                                      detail="No complete profile is supplied.")
        self.assertEqual(SelectorState(selection).confirm_start(unsupported).resolution, unsupported)
        with self.assertRaises(ValueError):
            PanelResolution(selection, SupportStatus.VALIDATED)
        with self.assertRaises(ValueError):
            PanelResolution(selection, SupportStatus.UNSUPPORTED, "not-allowed")


if __name__ == "__main__":
    unittest.main()
