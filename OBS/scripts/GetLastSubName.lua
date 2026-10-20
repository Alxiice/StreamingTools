-- # Last Follower
-- 

obs             = obslua

source_name     = ""
last_sub_path   = ""
last_resub_path = ""
refresh_s       = 15
refresh_ms      = refresh_s*1000
last_text       = ""
activated       = false

----------------------------------------------------------
-- Read entire file content
----------------------------------------------------------
function read_file(path)
    local file = io.open(path, "r")
    if file == nil then
        return "File not found"
    end

    local content = file:read("*all")
    file:close()

    if content == nil or content == "" then
        return ""
    end

    return content
end

----------------------------------------------------------
-- Update text source
----------------------------------------------------------
function update_text()
    if file_path == "" then
        return
    end

    local sub   = read_file(last_sub_path)
    local resub = read_file(last_sub_path)

    if text ~= last_text then
        local source = obs.obs_get_source_by_name(source_name)
        if source ~= nil then
            local settings = obs.obs_data_create()
            obs.obs_data_set_string(settings, "text", text)
            obs.obs_source_update(source, settings)
            obs.obs_data_release(settings)
            obs.obs_source_release(source)
        end

        last_text = text
    end
end

----------------------------------------------------------
-- Timer callback
----------------------------------------------------------
function timer_callback()
    update_text()
end

----------------------------------------------------------
-- Activate / Deactivate
----------------------------------------------------------
function activate(activating)
    if activated == activating then
        return
    end

    activated = activating

    if activating then
        update_text()
        obs.timer_add(timer_callback, refresh_ms)
    else
        obs.timer_remove(timer_callback)
    end
end

function activate_signal(cd, activating)
    local source = obs.calldata_source(cd, "source")
    if source ~= nil then
        local name = obs.obs_source_get_name(source)
        if name == source_name then
            activate(activating)
        end
    end
end

function source_activated(cd)
    activate_signal(cd, true)
end

function source_deactivated(cd)
    activate_signal(cd, false)
end

----------------------------------------------------------
-- OBS Properties UI
----------------------------------------------------------
function script_properties()
    local props = obs.obs_properties_create()

    -- File picker
    obs.obs_properties_add_path(
        props,
        "file_path",
        "Text File",
        obs.OBS_PATH_FILE,
        "Text Files (*.txt);;All Files (*.*)",
        nil
    )

    -- Refresh interval
    obs.obs_properties_add_int(
        props,
        "refresh_s",
        "Refresh Interval (s)",
        5,
		15,
		60
    )

    -- Text source selector
    local p = obs.obs_properties_add_list(
        props,
        "source",
        "Text Source",
        obs.OBS_COMBO_TYPE_EDITABLE,
        obs.OBS_COMBO_FORMAT_STRING
    )

    local sources = obs.obs_enum_sources()
    if sources ~= nil then
        for _, source in ipairs(sources) do
            local source_id = obs.obs_source_get_unversioned_id(source)
            if source_id == "text_gdiplus" or source_id == "text_ft2_source" then
                local name = obs.obs_source_get_name(source)
                obs.obs_property_list_add_string(p, name, name)
            end
        end
    end
    obs.source_list_release(sources)

    return props
end

----------------------------------------------------------
function script_description()
    return "Displays the contents of a text file inside a selected Text Source.\n\nUpdates automatically while the source is active."
end

----------------------------------------------------------
function script_update(settings)
    activate(false)

    source_name = obs.obs_data_get_string(settings, "source")
    file_path   = obs.obs_data_get_string(settings, "file_path")
    refresh_s  = obs.obs_data_get_int(settings, "refresh_s")

    last_text = ""
    activate(true)
end

----------------------------------------------------------
function script_load(settings)
    local sh = obs.obs_get_signal_handler()
    obs.signal_handler_connect(sh, "source_activate", source_activated)
    obs.signal_handler_connect(sh, "source_deactivate", source_deactivated)
end