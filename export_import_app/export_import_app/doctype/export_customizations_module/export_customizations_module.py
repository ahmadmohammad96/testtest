# Copyright (c) 2025, ahmadmohammad96 and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class ExportCustomizationsModule(Document):
	pass



import frappe
import json
import os
from datetime import datetime

class CustomJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder that can handle datetime objects"""
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.strftime('%Y-%m-%d %H:%M:%S')
        if hasattr(obj, 'as_dict'):
            return obj.as_dict()
        return super().default(obj)

def clean_doc_for_json(doc_data):
    """Clean document data to make it JSON serializable"""
    if doc_data is None:
        return None
        
    if isinstance(doc_data, dict):
        clean_data = {}
        for key, value in doc_data.items():
            # Handle datetime values
            if isinstance(value, datetime):
                clean_data[key] = value.strftime('%Y-%m-%d %H:%M:%S')
            # Handle nested dictionaries and lists
            elif isinstance(value, dict):
                clean_data[key] = clean_doc_for_json(value)
            elif isinstance(value, list):
                clean_data[key] = [clean_doc_for_json(item) for item in value]
            else:
                clean_data[key] = value
        return clean_data
    elif isinstance(doc_data, list):
        return [clean_doc_for_json(item) for item in doc_data]
    # Handle datetime values
    elif isinstance(doc_data, datetime):
        return doc_data.strftime('%Y-%m-%d %H:%M:%S')
    # Return the value as is for primitive types
    return doc_data

def get_client_script(script_name):
    """Get client script data (for backward compatibility)"""
    script = frappe.get_doc("Client Script", script_name)
    return {
        "name": script.name,
        "doctype_name": script.dt,
        "script": script.script,
        "enabled": script.enabled,
        "view": script.view,
        "module": script.module
    }

def get_server_script(script_name):
    """Get server script data (for backward compatibility)"""
    script = frappe.get_doc("Server Script", script_name)
    return {
        "name": script.name,
        "doctype_name": script.dt,
        "script_type": script.script_type,
        "script": script.script,
        "enabled": script.enabled,
        "module": script.module,
        "allow_guest": script.allow_guest
    }

@frappe.whitelist()
def export_customizations(doc_name):
    """
    Export customizations based on the settings in the Export Customizations Module
    
    Args:
        doc_name: Name of the Export Customizations Module document
        
    Returns:
        str: File document name of the exported customizations
    """
    try:
        doc = frappe.get_doc("Export Customizations Module", doc_name)
        
        # Generate timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Create a more organized export format
        export_data = {
            "doctype": "Customization",
            "sync_name": f"customization_export_{timestamp}",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "customizations": {}
        }
        
        # Export DocTypes customizations
        if doc.export_doctypes:
            doctypes_data = {}
            
            for dt_row in doc.export_doctypes:
                doctype_name = dt_row.doctype_name
                if not doctype_name:
                    continue
                
                frappe.log_error(f"Exporting: {doctype_name}", "Export")
                
                # Get doctype information
                is_custom = frappe.db.get_value("DocType", doctype_name, "custom") or 0
                is_single = frappe.db.get_value("DocType", doctype_name, "issingle") or 0
                
                # Create doctype entry
                doctypes_data[doctype_name] = {
                    "name": doctype_name,
                    "is_custom": is_custom,
                    "is_single": is_single,
                    "custom_fields": [],
                    "property_setters": []
                }
                
                # If it's a custom doctype or a single doctype, include full definition
                if is_custom or is_single or doctype_name == "Export Customizations Module":
                    # Get the doctype definition
                    try:
                        doctype_doc = frappe.get_doc("DocType", doctype_name)
                        doctypes_data[doctype_name]["doctype_definition"] = clean_doc_for_json(doctype_doc.as_dict())
                        
                        # Add fields data
                        fields_data = []
                        for field in doctype_doc.fields:
                            fields_data.append(clean_doc_for_json(field.as_dict()))
                        
                        doctypes_data[doctype_name]["fields"] = fields_data
                        
                        # For single doctypes, export the current values
                        if is_single:
                            try:
                                # Get the single doc values
                                single_doc = frappe.get_doc(doctype_name)
                                doctypes_data[doctype_name]["single_doc_values"] = clean_doc_for_json(single_doc.as_dict())
                                frappe.log_error(f"Exported single doctype values for {doctype_name}", "Export")
                            except Exception as e:
                                frappe.log_error(f"Error exporting single doctype values: {str(e)[:100]}", "Export")
                    except Exception as e:
                        frappe.log_error(f"Error exporting doctype definition: {str(e)[:100]}", "Export")
                
                # Get custom fields (if any)
                custom_fields = frappe.get_all(
                    "Custom Field",
                    filters={"dt": doctype_name},
                    fields=["*"]
                )
                
                for cf in custom_fields:
                    doctypes_data[doctype_name]["custom_fields"].append(clean_doc_for_json(cf))
                
                # Get property setters
                property_setters = frappe.get_all(
                    "Property Setter",
                    filters={"doc_type": doctype_name},
                    fields=["*"]
                )
                
                for ps in property_setters:
                    doctypes_data[doctype_name]["property_setters"].append(clean_doc_for_json(ps))
            
            export_data["customizations"]["doctypes"] = doctypes_data
        
        # Add Client Scripts
        if doc.all_client_scripts or (doc.export_client_scripts and len(doc.export_client_scripts) > 0):
            client_scripts_data = {}
            
            if doc.all_client_scripts:
                try:
                    # First check what fields are available
                    available_fields = []
                    for field in frappe.get_meta("Client Script").fields:
                        available_fields.append(field.fieldname)
                    
                    # Create a list of fields to fetch
                    fetch_fields = ["name"]
                    # Only include fields that exist
                    for field in ["dt", "doctype_or_field", "script", "enabled", "view", "module"]:
                        if field in available_fields:
                            fetch_fields.append(field)
                    
                    scripts = frappe.get_all("Client Script", fields=fetch_fields)
                    frappe.log_error(f"Client script fields: {fetch_fields}", "Export")
                    
                    for script in scripts:
                        client_scripts_data[script.name] = clean_doc_for_json(script)
                except Exception as e:
                    frappe.log_error(f"Error fetching client scripts: {str(e)[:100]}", "Export")
                    # Continue with the export even if scripts fail
            else:
                for script_row in doc.export_client_scripts:
                    script_name = script_row.client_script_name
                    if script_name:
                        try:
                            script_doc = frappe.get_doc("Client Script", script_name)
                            client_scripts_data[script_name] = clean_doc_for_json(script_doc)
                        except Exception as e:
                            frappe.log_error(f"Error fetching client script {script_name}: {str(e)[:100]}", "Export")
                            # Continue with other scripts
            
            export_data["customizations"]["client_scripts"] = client_scripts_data
        
        # Add Server Scripts
        if doc.all_server_scripts or (doc.export_server_scripts and len(doc.export_server_scripts) > 0):
            server_scripts_data = {}
            
            if doc.all_server_scripts:
                try:
                    # First check what fields are available
                    available_fields = []
                    for field in frappe.get_meta("Server Script").fields:
                        available_fields.append(field.fieldname)
                    
                    # Create a list of fields to fetch
                    fetch_fields = ["name"]
                    # Only include fields that exist
                    for field in ["reference_doctype", "dt", "doctype_or_field", "script_type", "script", "enabled", "module", "allow_guest"]:
                        if field in available_fields:
                            fetch_fields.append(field)
                    
                    scripts = frappe.get_all("Server Script", fields=fetch_fields)
                    frappe.log_error(f"Server script fields: {fetch_fields}", "Export")
                    
                    for script in scripts:
                        server_scripts_data[script.name] = clean_doc_for_json(script)
                except Exception as e:
                    frappe.log_error(f"Error fetching server scripts: {str(e)[:100]}", "Export")
                    # Continue with the export even if scripts fail
            else:
                for script_row in doc.export_server_scripts:
                    script_name = script_row.server_script_name
                    if script_name:
                        try:
                            script_doc = frappe.get_doc("Server Script", script_name)
                            server_scripts_data[script_name] = clean_doc_for_json(script_doc)
                        except Exception as e:
                            frappe.log_error(f"Error fetching server script {script_name}: {str(e)[:100]}", "Export")
                            # Continue with other scripts
            
            export_data["customizations"]["server_scripts"] = server_scripts_data
        
        # Save as File
        file_name = f"erpnext_customizations_{timestamp}.json"
        
        # Add debug info before saving
        frappe.log_error(f"Exporting {len(export_data['customizations'].get('doctypes', {}))} doctypes", "Export")
        
        # Check if we have any docs to export
        if len(export_data['customizations'].get('doctypes', {})) == 0 and \
           len(export_data['customizations'].get('client_scripts', {})) == 0 and \
           len(export_data['customizations'].get('server_scripts', {})) == 0:
            frappe.throw("No customizations found to export. Please check your selections.")
        
        try:
            file_content = json.dumps(export_data, indent=4, cls=CustomJSONEncoder)
        except Exception as json_error:
            frappe.log_error(f"JSON error: {str(json_error)[:100]}", "Export")
            raise
        
        file_doc = frappe.get_doc({
            "doctype": "File",
            "file_name": file_name,
            "content": file_content,
            "is_private": 1,
            "attached_to_doctype": "Export Customizations Module",
            "attached_to_name": doc_name
        })
        file_doc.insert()
        
        # Update the Export Customizations Module with latest file reference
        doc.db_set('last_export_file', file_doc.name)
        
        return file_doc.name
    except Exception as e:
        frappe.log_error(f"Export error: {str(e)[:100]}", "Export")
        frappe.throw(f"Error exporting: see the error logs for details")

@frappe.whitelist()
def send_customization_email(doc_name):
    """
    Send the exported customization file to all emails specified in the document
    
    Args:
        doc_name: Name of the Export Customizations Module document
        
    Returns:
        bool: True if email was sent successfully
    """
    try:
        doc = frappe.get_doc("Export Customizations Module", doc_name)
        
        # Check if we have a last export file
        file_name = doc.last_export_file
        
        # If not, find the latest file attached to this document
        if not file_name:
            files = frappe.get_all(
                "File",
                filters={
                    "attached_to_doctype": "Export Customizations Module",
                    "attached_to_name": doc_name
                },
                order_by="creation desc",
                limit=1
            )
            
            if not files:
                frappe.throw("No export file found. Please export customizations first.")
            
            file_name = files[0].name
        
        file_doc = frappe.get_doc("File", file_name)
        
        # Get email recipients
        recipients = []
        if doc.emails:
            for email_row in doc.emails:
                if email_row.email:
                    recipients.append(email_row.email)
        
        if not recipients:
            frappe.throw("No email recipients specified.")
        
        # Send email with attachment
        frappe.sendmail(
            recipients=recipients,
            subject=f"ERPNext Customizations Export - {doc.name}",
            message=f"""
                <p>Hello,</p>
                <p>Please find attached the exported ERPNext customizations as requested.</p>
                <p>This export was generated on {frappe.utils.get_datetime_str(frappe.utils.now())}.</p>
                <p>Regards,<br>ERPNext System</p>
            """,
            attachments=[{
                "fname": file_doc.file_name,
                "fcontent": file_doc.get_content()
            }]
        )
        
        return True
    except Exception as e:
        frappe.log_error(f"Error sending customization email: {str(e)}", "Export Customizations")
        frappe.throw(f"Error sending customization email: {str(e)}")