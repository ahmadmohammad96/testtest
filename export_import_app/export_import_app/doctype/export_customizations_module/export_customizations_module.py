# Copyright (c) 2025, ahmadmohammad96 and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class ExportCustomizationsModule(Document):
	pass
# Copyright (c) 2023, Your Name and contributors
# For license information, please see license.txt
# Copyright (c) 2023, Your Name and contributors
# For license information, please see license.txt

import frappe
import os
import json
import zipfile
import shutil
from frappe.model.document import Document
from frappe.utils import now_datetime, get_datetime, cint
from frappe.utils.file_manager import save_file

class ExportCustomizationsModule(Document):
	def validate(self):
		if not self.export_status:
			self.export_status = "Not Started"
			self.export_message = "Ready to export"
			self.last_export_update = now_datetime()

# Standalone function for document hooks
def validate(doc, method=None):
	if not doc.export_status:
		doc.export_status = "Not Started"
		doc.export_message = "Ready to export"
		doc.last_export_update = now_datetime()

class CustomizationExporter:
	def __init__(self, doc):
		self.doc = doc
		# Path for actual importable document fixtures
		self.fixtures_path = frappe.get_app_path("export_import_app", "fixtures")
		# Path for configuration/reference files (not importable)
		self.config_path = frappe.get_app_path("export_import_app", "config", "fixtures")
		
		# Create directories if they don't exist
		os.makedirs(self.fixtures_path, exist_ok=True)
		os.makedirs(self.config_path, exist_ok=True)
		
		self.exported_files = []
		self.export_timestamp = now_datetime().strftime("%Y%m%d%H%M%S")
			
	def update_status(self, status, message=""):
		"""Update the export status and message"""
		self.doc.export_status = status
		if message:
			self.doc.export_message = message
		self.doc.last_export_update = now_datetime()
		self.doc.save(ignore_permissions=True)
		frappe.db.commit()
	
	def _write_json_file(self, filename, data, is_document=True):
		"""Write data to a JSON file
		
		Args:
			filename (str): The name of the file
			data (dict or list): The data to write
			is_document (bool): Whether this is a document file (to be imported)
								or a config file (for reference only)
		"""
		# Choose the appropriate directory based on file type
		base_path = self.fixtures_path if is_document else self.config_path
		filepath = os.path.join(base_path, filename)
		
		try:
			# Validate documents have the required doctype field
			if is_document:
				if isinstance(data, dict):
					if "doctype" not in data:
						frappe.throw(f"Missing 'doctype' field in export data for {filename}")
				elif isinstance(data, list):
					for i, item in enumerate(data):
						if isinstance(item, dict) and "doctype" not in item:
							frappe.throw(f"Missing 'doctype' field in export data item {i} for {filename}")
			
			with open(filepath, 'w') as f:
				json.dump(data, f, indent=4, default=str)
			
			self.exported_files.append({
				"filename": filename,
				"filepath": filepath,
				"is_document": is_document
			})
			
			return filepath
		except Exception as e:
			frappe.log_error(f"Error writing to file {filename}: {str(e)}", "Customization Export")
			return None
	
	def export_doctypes(self):
		"""Export selected doctypes including their structure"""
		self.update_status("In Progress", "Exporting DocTypes...")
		
		for dt_row in self.doc.export_doctypes:
			doctype_name = dt_row.doctype_name
			try:
				# Get doctype definition
				doctype = frappe.get_doc("DocType", doctype_name)
				
				# Check if this is a core doctype or custom doctype
				is_core_doctype = cint(doctype.custom) == 0
				
				if not is_core_doctype:
					# Only export full definition for custom doctypes
					doctype_data = doctype.as_dict()
					
					# Remove unnecessary fields
					for field in ["creation", "modified", "modified_by", "owner", "docstatus"]:
						if field in doctype_data:
							del doctype_data[field]
					
					# Ensure doctype field is present (required for import)
					if "doctype" not in doctype_data:
						doctype_data["doctype"] = "DocType"
					
					# Export the doctype definition
					self._write_json_file(f"doctype_{doctype_name.lower().replace(' ', '_')}.json", doctype_data)
				
				# Export custom fields for this doctype
				self._export_custom_fields_for_doctype(doctype_name)
				
				# Export property setters for this doctype
				self._export_property_setters_for_doctype(doctype_name)
				
			except Exception as e:
				frappe.log_error(f"Error exporting doctype {doctype_name}: {str(e)}", "Customization Export")
				self.update_status("Completed with warnings", f"Error exporting doctype {doctype_name}: {str(e)}")
	
	def _export_custom_fields_for_doctype(self, doctype_name):
		"""Export custom fields for a specific doctype"""
		custom_fields = frappe.get_all(
			"Custom Field",
			filters={"dt": doctype_name},
			fields=["*"]
		)
		
		if custom_fields:
			formatted_custom_fields = []
			for cf in custom_fields:
				# Remove unnecessary fields
				for field in ["creation", "modified", "modified_by", "owner", "docstatus"]:
					if field in cf:
						del cf[field]
				
				# Ensure doctype field is present (required for import)
				cf["doctype"] = "Custom Field"
				formatted_custom_fields.append(cf)
			
			self._write_json_file(f"custom_fields_{doctype_name.lower().replace(' ', '_')}.json", formatted_custom_fields)
	
	def _export_property_setters_for_doctype(self, doctype_name):
		"""Export property setters for a specific doctype"""
		property_setters = frappe.get_all(
			"Property Setter",
			filters={"doc_type": doctype_name},
			fields=["*"]
		)
		
		if property_setters:
			formatted_property_setters = []
			for ps in property_setters:
				# Remove unnecessary fields
				for field in ["creation", "modified", "modified_by", "owner", "docstatus"]:
					if field in ps:
						del ps[field]
				
				# Ensure doctype field is present (required for import)
				ps["doctype"] = "Property Setter"
				formatted_property_setters.append(ps)
			
			self._write_json_file(f"property_setter_{doctype_name.lower().replace(' ', '_')}.json", formatted_property_setters)
	
	def export_client_scripts(self):
		"""Export selected client scripts"""
		self.update_status("In Progress", "Exporting Client Scripts...")
		
		client_scripts = []
		
		# If "All Client Scripts" is checked, get all client scripts
		if cint(self.doc.all_client_scripts):
			client_scripts = frappe.get_all("Client Script", fields=["*"])
		else:
			# Get only selected client scripts
			for cs_row in self.doc.export_client_scripts:
				cs = frappe.get_doc("Client Script", cs_row.client_script_name)
				client_scripts.append(cs.as_dict())
		
		if client_scripts:
			formatted_client_scripts = []
			for cs in client_scripts:
				# Remove unnecessary fields
				for field in ["creation", "modified", "modified_by", "owner", "docstatus"]:
					if field in cs:
						del cs[field]
				
				# Ensure doctype field is present (required for import)
				cs["doctype"] = "Client Script"
				formatted_client_scripts.append(cs)
			
			self._write_json_file("client_scripts.json", formatted_client_scripts)
	
	def export_server_scripts(self):
		"""Export selected server scripts"""
		self.update_status("In Progress", "Exporting Server Scripts...")
		
		server_scripts = []
		
		# If "All Server Scripts" is checked, get all server scripts
		if cint(self.doc.all_server_scripts):
			server_scripts = frappe.get_all("Server Script", fields=["*"])
		else:
			# Get only selected server scripts
			for ss_row in self.doc.export_server_scripts:
				ss = frappe.get_doc("Server Script", ss_row.server_script_name)
				server_scripts.append(ss.as_dict())
		
		if server_scripts:
			formatted_server_scripts = []
			for ss in server_scripts:
				# Remove unnecessary fields
				for field in ["creation", "modified", "modified_by", "owner", "docstatus"]:
					if field in ss:
						del ss[field]
				
				# Ensure doctype field is present (required for import)
				ss["doctype"] = "Server Script"
				formatted_server_scripts.append(ss)
			
			self._write_json_file("server_scripts.json", formatted_server_scripts)
	
	def create_fixtures_config(self):
		"""Create a fixtures configuration file to assist with imports"""
		# This is a configuration file, not a document, so use is_document=False
		config = {
			"export_info": {
				"app": "export_import_app",
				"timestamp": self.export_timestamp,
				"exported_by": frappe.session.user
			},
			"custom_doctypes": [],
			"custom_fields": {},
			"property_setters": {}
		}
		
		# Add exported doctypes to configuration
		for dt_row in self.doc.export_doctypes:
			doctype_name = dt_row.doctype_name
			doctype = frappe.get_doc("DocType", doctype_name)
			
			if cint(doctype.custom) == 1:
				config["custom_doctypes"].append(doctype_name)
			
			# Add custom fields
			custom_fields = frappe.get_all("Custom Field", filters={"dt": doctype_name}, fields=["fieldname"])
			if custom_fields:
				config["custom_fields"][doctype_name] = [cf.fieldname for cf in custom_fields]
			
			# Add property setters
			property_setters = frappe.get_all("Property Setter", filters={"doc_type": doctype_name}, fields=["property"])
			if property_setters:
				config["property_setters"][doctype_name] = [ps.property for ps in property_setters]
		
		# Write the configuration file - NOT a document, so use is_document=False
		self._write_json_file("export_references.json", config, is_document=False)
	
	def update_hooks_fixtures(self):
		"""Generate hooks.py fixtures configuration for easier imports"""
		
		# Create a fixtures configuration based on exported files
		fixtures_config = []
		
		# First add custom doctypes
		custom_doctypes = []
		for dt_row in self.doc.export_doctypes:
			doctype_name = dt_row.doctype_name
			try:
				doctype = frappe.get_doc("DocType", doctype_name)
				if cint(doctype.custom) == 1:
					custom_doctypes.append(doctype_name)
			except Exception:
				continue
		
		# Add custom doctypes as direct strings
		fixtures_config.extend(custom_doctypes)
		
		# Add custom fields configuration
		doctype_fields = {}
		for dt_row in self.doc.export_doctypes:
			doctype_name = dt_row.doctype_name
			custom_fields = frappe.get_all("Custom Field", filters={"dt": doctype_name})
			if custom_fields:
				if doctype_name not in doctype_fields:
					doctype_fields[doctype_name] = []
		
		if doctype_fields:
			fixtures_config.append({
				"dt": "Custom Field",
				"filters": [["dt", "in", list(doctype_fields.keys())]]
			})
		
		# Add property setter configuration
		doctype_props = {}
		for dt_row in self.doc.export_doctypes:
			doctype_name = dt_row.doctype_name
			property_setters = frappe.get_all("Property Setter", filters={"doc_type": doctype_name})
			if property_setters:
				if doctype_name not in doctype_props:
					doctype_props[doctype_name] = []
		
		if doctype_props:
			fixtures_config.append({
				"dt": "Property Setter",
				"filters": [["doc_type", "in", list(doctype_props.keys())]]
			})
		
		# Add client scripts configuration
		if cint(self.doc.all_client_scripts) or (self.doc.export_client_scripts and len(self.doc.export_client_scripts) > 0):
			fixtures_config.append({
				"dt": "Client Script",
				"filters": []
			})
		
		# Add server scripts configuration
		if cint(self.doc.all_server_scripts) or (self.doc.export_server_scripts and len(self.doc.export_server_scripts) > 0):
			fixtures_config.append({
				"dt": "Server Script",
				"filters": []
			})
		
		# Create a hooks.py sample file
		hooks_content = f"""
# Fixtures Configuration for export_import_app
# This is automatically generated based on your customization export

fixtures = {json.dumps(fixtures_config, indent=4, default=str)}
"""
		# Write to the config directory - NOT a document, so manually specify path
		hooks_sample_path = os.path.join(self.config_path, "hooks_template.py")
		with open(hooks_sample_path, 'w') as f:
			f.write(hooks_content)
			
		# Add to exported files list for tracking
		self.exported_files.append({
			"filename": "hooks_template.py",
			"filepath": hooks_sample_path,
			"is_document": False
		})
	
	def clear_previous_fixtures(self):
		"""Clear previous fixture files before export"""
		# Clear document fixtures
		for file in os.listdir(self.fixtures_path):
			if file.endswith('.json'):
				file_path = os.path.join(self.fixtures_path, file)
				if os.path.isfile(file_path):
					try:
						os.remove(file_path)
					except Exception as e:
						frappe.log_error(f"Error removing file {file_path}: {str(e)}", "Customization Export")
		
		# Clear config fixtures 
		for file in os.listdir(self.config_path):
			if file.endswith('.json') or file.endswith('.py'):
				file_path = os.path.join(self.config_path, file)
				if os.path.isfile(file_path):
					try:
						os.remove(file_path)
					except Exception as e:
						frappe.log_error(f"Error removing file {file_path}: {str(e)}", "Customization Export")
	
	def attach_files_to_doc(self):
		"""Attach the exported files to the document"""
		self.update_status("In Progress", "Attaching files to document...")
		
		# Create a timestamped ZIP filename for record-keeping
		zip_filename = f"customization_export_{self.export_timestamp}.zip"
		zip_filepath = os.path.join(frappe.get_site_path("private", "files"), zip_filename)
		
		# Create a zip file of all exported files
		with zipfile.ZipFile(zip_filepath, 'w') as zipf:
			# Add all files (both documents and configs)
			for file_info in self.exported_files:
				folder = "fixtures" if file_info.get("is_document", True) else "config"
				zipf.write(
					file_info["filepath"], 
					arcname=f"{folder}/{os.path.basename(file_info['filepath'])}"
				)
		
		# Attach the zip file to the document
		file_doc = save_file(
			zip_filename,
			open(zip_filepath, 'rb').read(),
			"Export Customizations Module",
			self.doc.name,
			is_private=1
		)
		
		# Update the last export file field
		self.doc.last_export_file = file_doc.name
		self.doc.save(ignore_permissions=True)
		
		return file_doc
	def send_emails(self, file_doc):
		"""Send emails with the exported files attached"""
		if not self.doc.emails or len(self.doc.emails) == 0:
			return
			
		self.update_status("In Progress", "Sending emails...")
		
		recipient_emails = [row.email for row in self.doc.emails if row.email]
		
		if not recipient_emails:
			return
			
		attachments = [{
			"fname": file_doc.file_name,
			"fcontent": file_doc.get_content()
		}]
		
		for email in recipient_emails:
			try:
				frappe.sendmail(
					recipients=[email],
					subject=f"ERPNext Customization Export - {self.export_timestamp}",
					message=f"Please find attached the customization export files generated on {self.doc.last_export_update}.",
					attachments=attachments
				)
			except Exception as e:
				frappe.log_error(f"Error sending email to {email}: {str(e)}", "Customization Export")
			

	def export_all(self):
		"""Run the complete export process"""
		try:
			self.update_status("Starting", "Starting export process...")
			
			# Clear previous fixture files
			self.clear_previous_fixtures()
			
			# Export the selected items
			self.export_doctypes()
			self.export_client_scripts()
			self.export_server_scripts()
			
			# Create configuration files
			self.create_fixtures_config()
			self.update_hooks_fixtures()
			
			# Attach files to the document
			file_doc = self.attach_files_to_doc()
			
			# Send emails if recipients are specified
			self.send_emails(file_doc)
			
			# Count exported files
			doc_files = sum(1 for f in self.exported_files if f.get("is_document", True))
			config_files = sum(1 for f in self.exported_files if not f.get("is_document", True))
			
			# Update export result with summary
			result = {
				"document_files": [f["filename"] for f in self.exported_files if f.get("is_document", True)],
				"config_files": [f["filename"] for f in self.exported_files if not f.get("is_document", True)],
				"timestamp": self.export_timestamp
			}
			
			self.doc.last_export_result = json.dumps(result, indent=4)
			self.update_status("Completed", f"Export completed successfully. {doc_files} document files and {config_files} config files exported.")
			
			return f"Export completed successfully. {doc_files} document files and {config_files} config files exported."
			
		except Exception as e:
			frappe.log_error(f"Export failed: {str(e)}", "Customization Export")
			self.update_status("Failed", f"Export failed: {str(e)}")
			return f"Export failed: {str(e)}"

@frappe.whitelist()
def export_customizations(docname):
	try:
		# Check if document exists and is saved
		if not docname or docname == "new-export-customizations-module":
			frappe.msgprint("Document must be saved before exporting")
			return "Document not saved"
			
		# Extra check - verify document exists in database  
		try:
			doc = frappe.get_doc("Export Customizations Module", docname)
		except frappe.DoesNotExistError:
			frappe.msgprint("Document must be saved before exporting")
			return "Document not saved"
			
		# Check if there's anything to export
		if (not doc.export_doctypes or len(doc.export_doctypes) == 0) and \
		(not cint(doc.all_client_scripts) and (not doc.export_client_scripts or len(doc.export_client_scripts) == 0)) and \
		(not cint(doc.all_server_scripts) and (not doc.export_server_scripts or len(doc.export_server_scripts) == 0)):
			frappe.msgprint("Nothing selected to export. Please select at least one doctype, client script, or server script.")
			return "Nothing to export"
		
		exporter = CustomizationExporter(doc)
		result = exporter.export_all()
		
		frappe.msgprint(result)
		return result
		
	except Exception as e:
		frappe.log_error(f"Export customizations failed: {str(e)}", "Customization Export")
		frappe.msgprint(f"Export failed: {str(e)}")
		return f"Export failed: {str(e)}"

@frappe.whitelist()
def get_doctypes_list():
	"""Get a list of non-custom doctypes for the selection field"""
	return frappe.get_all("DocType", filters={"custom": 0}, fields=["name"])

@frappe.whitelist()
def get_client_scripts_list():
	"""Get a list of client scripts for the selection field"""
	return frappe.get_all("Client Script", fields=["name"])

@frappe.whitelist()
def get_server_scripts_list():
	"""Get a list of server scripts for the selection field"""
	return frappe.get_all("Server Script", fields=["name"])