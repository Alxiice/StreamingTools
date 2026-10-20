import os
import obspython as obs

interval    = 15
source_name = ""

def set_source(_file):
	global source_name
	source_name = _file

# ------------------------------------------------------------

def update_text():
	global source_name
	if os.path.isfile(source_name):
		with open(source_name, "w") as f:
			data = obs.obs_data_create()
			obs.obs_data_set_string(data, "text", f.read())
			obs.obs_data_release(data)


def refresh_pressed(props, prop):
	update_text()

# ------------------------------------------------------------

def script_description():
	return "Load a text file"

def script_update(settings):
	global interval
	global source_name

	_file       = obs.obs_data_get_string(settings, "file")
	interval    = obs.obs_data_get_int(settings, "interval")

	obs.timer_remove(update_text)

	if _file != "":
		set_source(_file)
		obs.timer_add(update_text, interval * 1000)

def script_defaults(settings):
	obs.obs_data_set_default_int(settings, "interval", 15)

def script_properties():
	props = obs.obs_properties_create()

	obs.obs_properties_add_text(props, "file", "FILE", obs.OBS_TEXT_DEFAULT)
	obs.obs_properties_add_int(props, "interval", "Update Interval (seconds)", 5, 3600, 1)

	obs.obs_properties_add_button(props, "button", "Refresh", refresh_pressed)
	return props
