# Copyright (c) 2025, ahmadmohammad96 and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class ImportCustomizationsUI(Document):
	pass
import frappe
import json
from datetime import datetime

@frappe.whitelist()
def import_customizations(doc_name):
    """
    Import customizations from the attached JSON file
    
    Args:
        doc_name: Name of the Import Customizations UI document
        
    Returns:
        str: Summary of imported customizations
    """
    try:
        doc = frappe.get_doc("Import Customizations UI", doc_name)
        
        if not doc.json_file:
            frappe.throw("Please attach a customization JSON file first.")
        
        # Get the file content
        file_doc = frappe.get_doc("File", {"file_url": doc.json_file})
        if not file_doc:
            frappe.throw("Attached file not found.")
        
        # Parse the JSON content
        try:
            import_data = json.loads(file_doc.get_content().decode('utf-8'))
        except Exception as e:
            frappe.throw(f"Invalid JSON file: {str(e)}")
        
        # Validate the import data structure
        if not import_data.get("customizations"):
            frappe.throw("Invalid customization file format. Missing 'customizations' section.")
        
        # Start import process
        summary = {
            "doctypes_processed": 0,
            "custom_fields_created": 0,
            "custom_fields_updated": 0,
            "property_setters_created": 0,
            "property_setters_updated": 0,
            "client_scripts_created": 0,
            "client_scripts_updated": 0,
            "server_scripts_created": 0,
            "server_scripts_updated": 0,
            "custom_doctypes_created": 0,
            "custom_doctypes_updated": 0,
            "errors": []
        }
        
        # Process DocTypes customizations
        if "doctypes" in import_data["customizations"]:
            for doctype_name, doctype_data in import_data["customizations"]["doctypes"].items():
                try:
                    # Process DocType
                    summary["doctypes_processed"] += 1
                    
                    # 1. If it's a custom doctype, create or update it
                    if doctype_data.get("is_custom") and doctype_data.get("doctype_definition"):
                        try:
                            import_custom_doctype(doctype_data, summary)
                        except Exception as e:
                            summary["errors"].append(f"Error importing custom DocType {doctype_name}: {str(e)}")
                    
                    # 2. Process custom fields
                    if doctype_data.get("custom_fields"):
                        for custom_field in doctype_data["custom_fields"]:
                            try:
                                import_custom_field(custom_field, summary)
                            except Exception as e:
                                summary["errors"].append(f"Error importing Custom Field {custom_field.get('fieldname')} for {doctype_name}: {str(e)}")
                    
                    # 3. Process property setters
                    if doctype_data.get("property_setters"):
                        for property_setter in doctype_data["property_setters"]:
                            try:
                                import_property_setter(property_setter, summary)
                            except Exception as e:
                                summary["errors"].append(f"Error importing Property Setter {property_setter.get('property')} for {doctype_name}: {str(e)}")
                    
                    # 4. If single doctype, update its values
                    if doctype_data.get("is_single") and doctype_data.get("single_doc_values"):
                        try:
                            import_single_doc_values(doctype_name, doctype_data["single_doc_values"], summary)
                        except Exception as e:
                            summary["errors"].append(f"Error importing Single DocType values for {doctype_name}: {str(e)}")
                
                except Exception as e:
                    summary["errors"].append(f"Error processing DocType {doctype_name}: {str(e)}")
        
        # Process Client Scripts
        if "client_scripts" in import_data["customizations"]:
            for script_name, script_data in import_data["customizations"]["client_scripts"].items():
                try:
                    import_client_script(script_data, summary)
                except Exception as e:
                    summary["errors"].append(f"Error importing Client Script {script_name}: {str(e)}")
        
        # Process Server Scripts
        if "server_scripts" in import_data["customizations"]:
            for script_name, script_data in import_data["customizations"]["server_scripts"].items():
                try:
                    import_server_script(script_data, summary)
                except Exception as e:
                    summary["errors"].append(f"Error importing Server Script {script_name}: {str(e)}")
        
        # Generate summary text
        summary_text = f"""
        Import completed with the following results:
        
        DocTypes processed: {summary["doctypes_processed"]}
        Custom DocTypes created: {summary["custom_doctypes_created"]}
        Custom DocTypes updated: {summary["custom_doctypes_updated"]}
        Custom Fields created: {summary["custom_fields_created"]}
        Custom Fields updated: {summary["custom_fields_updated"]}
        Property Setters created: {summary["property_setters_created"]}
        Property Setters updated: {summary["property_setters_updated"]}
        Client Scripts created: {summary["client_scripts_created"]}
        Client Scripts updated: {summary["client_scripts_updated"]}
        Server Scripts created: {summary["server_scripts_created"]}
        Server Scripts updated: {summary["server_scripts_updated"]}
        
        Errors: {len(summary["errors"])}
        """
        
        # Log detailed summary including errors
        frappe.log_error(
            f"Import Summary: {summary_text}\n\nDetailed Errors: {json.dumps(summary['errors'], indent=2)}",
            "Customization Import"
        )
        
        # Store import results in the document
        doc.db_set('last_import_result', summary_text)
        doc.db_set('last_import_date', datetime.now())
        
        return summary_text
    
    except Exception as e:
        frappe.log_error(f"Import error: {str(e)}", "Customization Import")
        frappe.throw(f"Error importing customizations: {str(e)}")

def import_custom_doctype(doctype_data, summary):
    """Import a custom DocType"""
    doctype_name = doctype_data["name"]
    doctype_exists = frappe.db.exists("DocType", doctype_name)
    
    # Prepare DocType data
    doctype_def = doctype_data["doctype_definition"]
    
    # Remove system fields that shouldn't be set directly
    for field in ["creation", "modified", "owner", "modified_by", "docstatus", "idx"]:
        if field in doctype_def:
            del doctype_def[field]
    
    if doctype_exists:
        # Update existing DocType
        doc = frappe.get_doc("DocType", doctype_name)
        
        # Update fields based on the new definition
        for key, value in doctype_def.items():
            if key != "fields" and hasattr(doc, key):
                setattr(doc, key, value)
        
        # Handle fields separately since they are child DocTypes
        if "fields" in doctype_data:
            # First, remove all existing fields
            doc.fields = []
            
            # Then add all fields from the import
            for field_data in doctype_data["fields"]:
                # Clean field data
                for field in ["creation", "modified", "owner", "modified_by", "docstatus", "idx"]:
                    if field in field_data:
                        del field_data[field]
                
                doc.append("fields", field_data)
        
        # Save DocType with ignore_permissions
        doc.save(ignore_permissions=True)
        summary["custom_doctypes_updated"] += 1
    else:
        # Create new DocType
        doc = frappe.new_doc("DocType")
        
        # Set basic properties
        for key, value in doctype_def.items():
            if key != "fields" and hasattr(doc, key):
                setattr(doc, key, value)
        
        # Add fields
        if "fields" in doctype_data:
            for field_data in doctype_data["fields"]:
                # Clean field data
                for field in ["creation", "modified", "owner", "modified_by", "docstatus", "idx"]:
                    if field in field_data:
                        del field_data[field]
                
                doc.append("fields", field_data)
        
        # Save DocType with ignore_permissions
        doc.insert(ignore_permissions=True)
        summary["custom_doctypes_created"] += 1
    
    # Clear cache to ensure changes are reflected
    frappe.clear_cache(doctype=doctype_name)

def import_custom_field(field_data, summary):
    """Import a Custom Field"""
    # Check if the field already exists
    field_exists = False
    existing_field_name = None
    
    if field_data.get("name"):
        field_exists = frappe.db.exists("Custom Field", field_data["name"])
        if field_exists:
            existing_field_name = field_data["name"]
    
    if not field_exists and field_data.get("fieldname") and field_data.get("dt"):
        # Try to find by fieldname and doctype
        existing_fields = frappe.get_all("Custom Field", 
            filters={
                "fieldname": field_data["fieldname"],
                "dt": field_data["dt"]
            }
        )
        if existing_fields:
            field_exists = True
            existing_field_name = existing_fields[0].name
    
    # Remove system fields
    for field in ["creation", "modified", "owner", "modified_by", "docstatus", "idx"]:
        if field in field_data:
            del field_data[field]
    
    if field_exists and existing_field_name:
        # Update existing field
        doc = frappe.get_doc("Custom Field", existing_field_name)
        
        # Update field properties
        for key, value in field_data.items():
            if hasattr(doc, key):
                setattr(doc, key, value)
        
        doc.save(ignore_permissions=True)
        summary["custom_fields_updated"] += 1
    else:
        # Create new custom field
        doc = frappe.new_doc("Custom Field")
        
        # Set field properties
        for key, value in field_data.items():
            if hasattr(doc, key):
                setattr(doc, key, value)
        
        doc.insert(ignore_permissions=True)
        summary["custom_fields_created"] += 1
    
    # Clear cache to ensure changes are reflected
    if field_data.get("dt"):
        frappe.clear_cache(doctype=field_data["dt"])

def import_property_setter(property_data, summary):
    """Import a Property Setter"""
    # Check if property setter already exists
    property_exists = False
    existing_property_name = None
    
    if property_data.get("name"):
        property_exists = frappe.db.exists("Property Setter", property_data["name"])
        if property_exists:
            existing_property_name = property_data["name"]
    
    if not property_exists and property_data.get("doc_type") and property_data.get("property"):
        # Try to find by doctype, property, and additional criteria
        filters = {
            "doc_type": property_data["doc_type"],
            "property": property_data["property"]
        }
        
        # Add additional filters based on available fields
        if property_data.get("doctype_or_field"):
            filters["doctype_or_field"] = property_data["doctype_or_field"]
        
        if property_data.get("field_name"):
            filters["field_name"] = property_data["field_name"]
        
        existing_properties = frappe.get_all("Property Setter", filters=filters)
        if existing_properties:
            property_exists = True
            existing_property_name = existing_properties[0].name
    
    # Remove system fields
    for field in ["creation", "modified", "owner", "modified_by", "docstatus", "idx"]:
        if field in property_data:
            del property_data[field]
    
    if property_exists and existing_property_name:
        # Update existing property setter
        doc = frappe.get_doc("Property Setter", existing_property_name)
        
        # Update properties
        for key, value in property_data.items():
            if hasattr(doc, key):
                setattr(doc, key, value)
        
        doc.save(ignore_permissions=True)
        summary["property_setters_updated"] += 1
    else:
        # Create new property setter
        doc = frappe.new_doc("Property Setter")
        
        # Set properties
        for key, value in property_data.items():
            if hasattr(doc, key):
                setattr(doc, key, value)
        
        doc.insert(ignore_permissions=True)
        summary["property_setters_created"] += 1
    
    # Clear cache to ensure changes are reflected
    if property_data.get("doc_type"):
        frappe.clear_cache(doctype=property_data["doc_type"])

def import_single_doc_values(doctype_name, values_data, summary):
    """Import values for a Single DocType"""
    if not frappe.db.exists("DocType", doctype_name):
        raise Exception(f"DocType {doctype_name} not found")
    
    doctype = frappe.get_meta(doctype_name)
    if not doctype.issingle:
        raise Exception(f"DocType {doctype_name} is not a Single DocType")
    
    # Get the doc
    doc = frappe.get_doc(doctype_name)
    
    # Update values
    for key, value in values_data.items():
        # Skip system fields
        if key in ["creation", "modified", "owner", "modified_by", "docstatus", "idx", "name", "doctype"]:
            continue
        
        if hasattr(doc, key):
            setattr(doc, key, value)
    
    doc.save(ignore_permissions=True)
    
    # Clear cache
    frappe.clear_cache(doctype=doctype_name)

def import_client_script(script_data, summary):
    """Import a Client Script"""
    # Check if script already exists
    script_exists = False
    existing_script_name = None
    
    if script_data.get("name"):
        script_exists = frappe.db.exists("Client Script", script_data["name"])
        if script_exists:
            existing_script_name = script_data["name"]
    
    # If not found by name, try to find by doctype (dt)
    if not script_exists and script_data.get("dt"):
        # For Client Scripts, usually there is one per doctype/view combination
        filters = {"dt": script_data["dt"]}
        
        if script_data.get("view"):
            filters["view"] = script_data["view"]
            
        existing_scripts = frappe.get_all("Client Script", filters=filters)
        if existing_scripts:
            script_exists = True
            existing_script_name = existing_scripts[0].name
    
    # Remove system fields
    for field in ["creation", "modified", "owner", "modified_by", "docstatus", "idx"]:
        if field in script_data:
            del script_data[field]
    
    if script_exists and existing_script_name:
        # Update existing script
        doc = frappe.get_doc("Client Script", existing_script_name)
        
        # Update properties
        for key, value in script_data.items():
            if hasattr(doc, key):
                setattr(doc, key, value)
        
        doc.save(ignore_permissions=True)
        summary["client_scripts_updated"] += 1
    else:
        # Create new client script
        doc = frappe.new_doc("Client Script")
        
        # Set properties
        for key, value in script_data.items():
            if hasattr(doc, key):
                setattr(doc, key, value)
        
        doc.insert(ignore_permissions=True)
        summary["client_scripts_created"] += 1
    
    # Clear cache
    if script_data.get("dt"):
        frappe.clear_cache(doctype=script_data["dt"])

def import_server_script(script_data, summary):
    """Import a Server Script"""
    # Check if script already exists
    script_exists = False
    existing_script_name = None
    
    if script_data.get("name"):
        script_exists = frappe.db.exists("Server Script", script_data["name"])
        if script_exists:
            existing_script_name = script_data["name"]
    
    # If not found by name, try to find by doctype and script_type
    filters = {}
    if not script_exists:
        # Handle different field names for doctype reference
        if script_data.get("reference_doctype"):
            filters["reference_doctype"] = script_data["reference_doctype"]
        elif script_data.get("dt"):
            filters["reference_doctype"] = script_data["dt"]
        
        if script_data.get("script_type"):
            filters["script_type"] = script_data["script_type"]
        
        if filters:
            existing_scripts = frappe.get_all("Server Script", filters=filters)
            if existing_scripts:
                script_exists = True
                existing_script_name = existing_scripts[0].name
    
    # Remove system fields
    for field in ["creation", "modified", "owner", "modified_by", "docstatus", "idx"]:
        if field in script_data:
            del script_data[field]
    
    if script_exists and existing_script_name:
        # Update existing script
        doc = frappe.get_doc("Server Script", existing_script_name)
        
        # Update properties
        for key, value in script_data.items():
            if hasattr(doc, key):
                setattr(doc, key, value)
        
        doc.save(ignore_permissions=True)
        summary["server_scripts_updated"] += 1
    else:
        # Create new server script
        doc = frappe.new_doc("Server Script")
        
        # Set properties
        for key, value in script_data.items():
            if hasattr(doc, key):
                setattr(doc, key, value)
        
        doc.insert(ignore_permissions=True)
        summary["server_scripts_created"] += 1
    
    # Clear cache to ensure changes are reflected
    doctype_to_clear = None
    if script_data.get("reference_doctype"):
        doctype_to_clear = script_data["reference_doctype"]
    elif script_data.get("dt"):
        doctype_to_clear = script_data["dt"]
    
    if doctype_to_clear:
        frappe.clear_cache(doctype=doctype_to_clear)