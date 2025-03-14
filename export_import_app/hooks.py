app_name = "export_import_app"
app_title = "Export Import App"
app_publisher = "ahmadmohammad96"
app_description = "export and import"
app_email = "ahmad900mohammad@gmail.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "export_import_app",
# 		"logo": "/assets/export_import_app/logo.png",
# 		"title": "Export Import App",
# 		"route": "/export_import_app",
# 		"has_permission": "export_import_app.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/export_import_app/css/export_import_app.css"
# app_include_js = "/assets/export_import_app/js/export_import_app.js"

# include js, css files in header of web template
# web_include_css = "/assets/export_import_app/css/export_import_app.css"
# web_include_js = "/assets/export_import_app/js/export_import_app.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "export_import_app/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "export_import_app/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "export_import_app.utils.jinja_methods",
# 	"filters": "export_import_app.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "export_import_app.install.before_install"
# after_install = "export_import_app.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "export_import_app.uninstall.before_uninstall"
# after_uninstall = "export_import_app.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "export_import_app.utils.before_app_install"
# after_app_install = "export_import_app.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "export_import_app.utils.before_app_uninstall"
# after_app_uninstall = "export_import_app.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "export_import_app.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"export_import_app.tasks.all"
# 	],
# 	"daily": [
# 		"export_import_app.tasks.daily"
# 	],
# 	"hourly": [
# 		"export_import_app.tasks.hourly"
# 	],
# 	"weekly": [
# 		"export_import_app.tasks.weekly"
# 	],
# 	"monthly": [
# 		"export_import_app.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "export_import_app.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "export_import_app.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "export_import_app.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["export_import_app.utils.before_request"]
# after_request = ["export_import_app.utils.after_request"]

# Job Events
# ----------
# before_job = ["export_import_app.utils.before_job"]
# after_job = ["export_import_app.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"export_import_app.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }
# Fixtures
# --------
# These are the standard fixtures that will be created/imported during app installation
doc_events = {
    "Export Customizations Module": {
        "validate": "export_import_app.export_import_app.doctype.export_customizations_module.export_customizations_module.validate"
    }
}

# Fixtures
# --------
# These are the standard fixtures that will be created/imported during app installation
fixtures = [
    # Include the export module doctypes in fixtures
    "Export Customizations Module",
    "Export Customizations Child Doctypes",
    "Export Customizations Child Client Scripts", 
    "Export Customizations Child Server Scripts",
    "Predefined Emails Child Table",
]

# The fixtures that are generated by the export tool will be stored in the standard directory
# They will be automatically imported when this app is installed on another site

# Create fixture directories if they don't exist
import os
from frappe.utils import get_bench_path
import frappe

def create_fixture_dirs():
    try:
        app_path = os.path.join(get_bench_path(), 'apps', 'export_import_app', 'export_import_app')
        fixtures_path = os.path.join(app_path, 'fixtures')
        
        # Create fixtures directory if it doesn't exist
        if not os.path.exists(fixtures_path):
            os.makedirs(fixtures_path)
            print(f"Created fixtures directory at {fixtures_path}")
            
    except Exception as e:
        print(f"Error creating fixtures directory: {str(e)}")

# Call the function when hooks.py is loaded
create_fixture_dirs()