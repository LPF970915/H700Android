-- Optional KOReader GitHub-build user patch for the H700 Android product.
-- Priority 2: Device.input must already be initialized before editing its map.
-- Enables its existing D-pad UI; changes no Android setting or global key map.
-- Select: menu. Start: file browser. A/Enter: confirm. B: back.
local ok, android = pcall(require, "android")
-- KOReader normalizes Android model names to lowercase.
if not ok or (tostring(android.prop.model):lower():gsub("[%W_]", "") ~= "rgsph700") then
    return
end
local Device = require("device")
Device.hasDPad = function() return true end
-- The panel is already in its native landscape orientation.
Device.input:disableRotationMap()
local keys = Device.input.event_map
keys[66] = "Press"
keys[96] = "Press"
keys[97] = "Back"
keys[109] = "Menu"
keys[108] = "Home"
-- UIManager loaded FocusManager before late patches. Refresh its cached key
-- mappings through the same method used when a physical keyboard is attached.
local FocusManager = require("ui/widget/focusmanager")
local refresh = FocusManager:new{layout = {}}
refresh:onPhysicalKeyboardConnected()
FocusManager.FOCUS_ONLY_ON_NT = 0
require("logger").info("H700 KOReader D-pad profile enabled")
-- Translate Android joystick HAT motion into KOReader's existing direction keys.
-- NativeActivity receives the handheld D-pad as a motion source, not keyboard.
-- Ignore analog sticks here; menu/page navigation needs only the digital HAT.
local ffi = require("ffi")
local bit = require("bit")
ffi.cdef[[
    int32_t AInputEvent_getSource(const void* event);
    float AMotionEvent_getAxisValue(const void* event, int32_t axis, size_t pointer_index);
]]
local backend = require("ffi/input_android")
local patch = require("userpatch")
local old_motion, motion_idx = patch.getUpValue(backend.waitForEvent, "motionEventHandler")
local key_handler = patch.getUpValue(backend.waitForEvent, "keyEventHandler")
local emit = key_handler and patch.getUpValue(key_handler, "genEmuEvent")
if type(old_motion) ~= "function" or type(emit) ~= "function" then
    require("logger").warn("H700 HAT bridge unavailable; upstream input API changed")
    return
end
local held = { [15] = 0, [16] = 0 }
local next_repeat = { [15] = 0, [16] = 0 }
local function hat_motion(event)
    local source = android.lib.AInputEvent_getSource(event)
    if bit.band(source, 0x01000000) == 0 then
        return old_motion(event)
    end
    local ts = android.lib.AMotionEvent_getEventTime(event)
    local now = tonumber(ts) / 1e9
    for axis = 15, 16 do
        local value = android.lib.AMotionEvent_getAxisValue(event, axis, 0)
        local direction = value < -0.5 and -1 or (value > 0.5 and 1 or 0)
        if direction ~= 0 and (direction ~= held[axis] or now >= next_repeat[axis]) then
            local code = axis == 15 and (direction < 0 and 21 or 22) or (direction < 0 and 19 or 20)
            emit(1, code, 1, nil, ts)
            emit(1, code, 0, nil, ts)
            next_repeat[axis] = now + (direction ~= held[axis] and 0.45 or 0.18)
            require("logger").dbg("H700 HAT direction", code)
        end
        held[axis] = direction
    end
end
patch.replaceUpValue(backend.waitForEvent, motion_idx, hat_motion)
require("logger").info("H700 KOReader HAT bridge enabled")
-- File chooser: use Left/Right for list pages when there is only one column.
-- Keep the normal focus behavior in toolbars and multi-column dialogs.
local Menu = require("ui/widget/menu")
local old_focus_move = Menu.onFocusMove
function Menu:onFocusMove(args)
    local row = self.layout and self.selected and self.layout[self.selected.y]
    if self.path_items and self.page_num and self.page_num > 1 and row and #row == 1 and args[1] ~= 0 then
        if args[1] > 0 then return self:onNextPage() end
        return self:onPrevPage()
    end
    return old_focus_move(self, args)
end
-- Use KOReader's built-in file-browser return policy on the first setup.
-- A later explicit user choice is preserved.
if not G_reader_settings:has("h700_dpad_original_back_in_reader") then
    G_reader_settings:saveSetting("h700_dpad_original_back_in_reader", G_reader_settings:readSetting("back_in_reader", "previous_location"))
    G_reader_settings:saveSetting("back_in_reader", "filebrowser")
end
-- EPUB/TXT font size shortcuts use the reader's existing ChangeSize event.
-- The graphical size selector is not fully focusable in this upstream build.
keys[102] = "H700FontSmaller"
keys[103] = "H700FontLarger"
local ReaderUI = require("apps/reader/readerui")
local old_register_keys = ReaderUI.registerKeyEvents
function ReaderUI:registerKeyEvents()
    old_register_keys(self)
    self.key_events.H700FontSmaller = { { "H700FontSmaller" }, event = "ChangeSize", args = -2 }
    self.key_events.H700FontLarger = { { "H700FontLarger" }, event = "ChangeSize", args = 2 }
end
ReaderUI.onPhysicalKeyboardConnected = ReaderUI.registerKeyEvents
