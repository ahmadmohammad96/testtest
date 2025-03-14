# Copyright (c) 2025, ahmadmohammad96 and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class ExportCustomizationsModule(Document):
	pass

import frappe
import os
import json
import subprocess
import time
import signal
import re
from frappe.utils import get_files_path, cstr, now, now_datetime
from frappe.utils.file_manager import save_file
from frappe.utils.background_jobs import enqueue
import sys

@frappe.whitelist()
def export_customizations(doctype_name, export_doc):
    """
    Main function to export customizations:
    1. Queue a background job to handle the export
    2. Return immediately to prevent timeout
    """
    try:
        export_doc = json.loads(export_doc)
        
        # Enqueue the actual export as a background job
        enqueue(
            execute_export_customizations,
            queue='long',
            timeout=1800,  # 30 minutes timeout
            event='export_customizations',
            doctype_name=doctype_name,
            export_doc=export_doc,
            job_name=f"export_customizations_{doctype_name}_{time.time()}"
        )
        
        return {
            "message": "Export process started in background",
            "background_job": True
        }
    except Exception as e:
        frappe.log_error(title="Export Customizations Error", message=frappe.get_traceback())
        frappe.throw(f"Error starting export process: {str(e)}")

# Changes to execute_export_customizations for improved auto-saving
def execute_export_customizations(doctype_name, export_doc):
    """
    The actual export process that runs in the background
    """
    try:
        frappe.db.commit()  # To ensure we're working with a fresh transaction
        
        # Explicitly store the export_doc in frappe.local for access in subprocesses
        if not hasattr(frappe.local, 'form_dict'):
            frappe.local.form_dict = {}
        frappe.local.form_dict['kwargs'] = json.dumps({'export_doc': export_doc})
        
        # Update status - Starting
        update_export_status(doctype_name, "In Progress", "Starting export process...")
        
        # Get app information
        app_info = get_custom_app_info()
        if not app_info:
            update_export_status(doctype_name, "Failed", "Could not determine app to update")
            frappe.db.commit()
            return
        
        # Update status - Updating hooks
        update_export_status(doctype_name, "In Progress", "Updating hooks.py with fixtures configuration...")
        
        # Update hooks.py with fixtures
        update_hooks_file(app_info, export_doc)
        
        # Update status - Running export
        update_export_status(doctype_name, "In Progress", "Running export fixtures process...")
        
        # Run custom export fixtures with proper data access
        exported_files = export_fixtures_handler(app_info, export_doc)
        
        # Check for any remaining empty JSON files and try to fix them
        fix_empty_json_files(app_info, export_doc)
        
        # Get final list of all valid exported files
        fixtures_path = os.path.join(app_info["path"], app_info["name"], "fixtures")
        all_exported_files = []
        for root, dirs, files in os.walk(fixtures_path):
            for file in files:
                if file.endswith('.json'):
                    file_path = os.path.join(root, file)
                    # Only include valid non-empty files
                    try:
                        if os.path.getsize(file_path) > 5:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                                if content.strip() and content.strip() not in ['{}', '[]']:
                                    # Try to parse it to confirm it's valid JSON
                                    json.loads(content)
                                    all_exported_files.append(file_path)
                    except:
                        # If there's any issue, skip this file
                        pass
        
        if not all_exported_files:
            update_export_status(doctype_name, "Completed with warnings", "No valid fixtures were exported")
            frappe.db.commit()
            return
        
        # Update status - Saving files
        update_export_status(doctype_name, "In Progress", f"Saving {len(all_exported_files)} exported files...")
        
        # Save exported files in File DocType
        file_links = save_exported_files(all_exported_files, doctype_name)
        
        # Send emails if specified
        if export_doc.get('emails') and file_links:
            update_export_status(doctype_name, "In Progress", "Sending email notifications...")
            send_exported_files_email(export_doc['emails'], file_links, doctype_name)
        
        # Update final status
        update_export_status(
            doctype_name, 
            "Completed", 
            f"Export completed successfully. {len(file_links)} files exported."
        )
        frappe.db.commit()
        
        # Add the results to the doctype directly for retrieval
        doc = frappe.get_doc("Export Customizations Module", doctype_name)
        doc.db_set('last_export_result', json.dumps({"files": file_links}))
        doc.add_comment('Comment', text=f"Export completed successfully. {len(file_links)} files exported.")
        
        # Use multiple approaches to ensure the document is saved
        try:
            # Method 1: Direct SQL update to set modified timestamp
            frappe.db.sql("""
                UPDATE `tabExport Customizations Module`
                SET modified = %s,
                    modified_by = %s
                WHERE name = %s
            """, (
                now(), 
                frappe.session.user,
                doctype_name
            ))
            frappe.db.commit()
            
            # Method 2: Reload and save the document with minimum validation
            try:
                doc.reload()
                doc.flags.ignore_permissions = True
                doc.flags.ignore_version = True
                doc.flags.ignore_validate = True
                doc.flags.ignore_links = True
                doc.flags.ignore_mandatory = True
                
                # Set a dummy field to force a save
                if hasattr(doc, 'export_message'):
                    current_msg = doc.export_message
                    doc.export_message = current_msg + " "
                
                doc.save(ignore_permissions=True)
                frappe.db.commit()
            except Exception as save_error:
                safe_log(f"Method 2 save failed: {str(save_error)}")
                
            # Method 3: Try db_set with update_modified flag
            try:
                doc.db_set('export_status', 'Completed', update_modified=True)
                frappe.db.commit()
            except Exception as db_set_error:
                safe_log(f"Method 3 save failed: {str(db_set_error)}")
                
            safe_log(f"Document {doctype_name} saved via multiple methods", "Auto Save")
        except Exception as save_error:
            safe_log(f"All save methods failed: {str(save_error)}", "Auto Save Error")
            frappe.db.commit()
        
    except Exception as e:
        error_msg = f"Error in export process: {str(e)[:200]}"  # Limit error message length
        safe_log(title="Export Error", message=frappe.get_traceback())
        update_export_status(doctype_name, "Failed", error_msg)
        
        # Add error comment
        try:
            doc = frappe.get_doc("Export Customizations Module", doctype_name)
            doc.add_comment('Comment', text=f"Export failed: {error_msg}")
        except:
            pass
        
        frappe.db.commit()

def update_export_status(doctype_name, status, message):
    """Update the export status in the document"""
    try:
        doc = frappe.get_doc("Export Customizations Module", doctype_name)
        doc.db_set('export_status', status)
        doc.db_set('export_message', message[:200] if message else "")  # Limit message length
        doc.db_set('last_export_update', frappe.utils.now())
        frappe.db.commit()
        
        # Also log for debugging - use the safe version
        safe_log(f"Export status update: {status} - {message}", "Export Status")
    except Exception as e:
        safe_log(f"Failed to update export status: {str(e)}", "Export Status Error")

def get_custom_app_info():
    """Find a suitable custom app to store fixtures"""
    # Try common custom app names
    bench_path = get_bench_path()
    common_custom_apps = ["export_import_app", "custom_app", "custom", "erpnext_custom"]
    
    for app_name in common_custom_apps:
        app_path = os.path.join(bench_path, "apps", app_name)
        if os.path.exists(app_path):
            return {
                "name": app_name,
                "path": app_path
            }
    
    # If no custom app found, try to find any app other than frappe and erpnext
    apps_dir = os.path.join(bench_path, "apps")
    if os.path.exists(apps_dir):
        for app_name in os.listdir(apps_dir):
            if app_name not in ["frappe", "erpnext"] and os.path.isdir(os.path.join(apps_dir, app_name)):
                return {
                    "name": app_name,
                    "path": os.path.join(apps_dir, app_name)
                }
    
    # Fall back to erpnext if available
    erpnext_path = os.path.join(bench_path, "apps", "erpnext")
    if os.path.exists(erpnext_path):
        return {
            "name": "erpnext",
            "path": erpnext_path
        }
    
    return None

def get_bench_path():
    """Get the bench directory path"""
    # First try using frappe's utility if available
    try:
        from frappe.utils import get_bench_path as fbp
        return fbp()
    except:
        pass
    
    # Fallback method - derive from frappe site path
    site_path = frappe.get_site_path()
    # Remove 'sites/sitename' from the path to get bench path
    bench_path = os.path.abspath(os.path.join(site_path, '..', '..'))
    
    # Verify this is actually a bench directory
    if os.path.exists(os.path.join(bench_path, 'apps')) and os.path.exists(os.path.join(bench_path, 'sites')):
        return bench_path
    
    # Another fallback - use current working directory if it looks like a bench
    cwd = os.getcwd()
    if os.path.exists(os.path.join(cwd, 'apps')) and os.path.exists(os.path.join(cwd, 'sites')):
        return cwd
    
    # One more try - go up from the site directory until we find a directory with apps and sites subdirectories
    current_dir = site_path
    for _ in range(5):  # Limit the number of parent directories to check
        parent_dir = os.path.abspath(os.path.join(current_dir, '..'))
        if parent_dir == current_dir:  # We've reached the root
            break
        
        if os.path.exists(os.path.join(parent_dir, 'apps')) and os.path.exists(os.path.join(parent_dir, 'sites')):
            return parent_dir
        
        current_dir = parent_dir
    
    frappe.throw("Could not determine bench path. Please run this from within a Frappe bench.")

def update_hooks_file(app_info, export_doc):
    """Update the hooks.py file with fixtures based on user selection"""
    hooks_path = os.path.join(app_info["path"], app_info["name"], "hooks.py")
    
    if not os.path.exists(hooks_path):
        frappe.throw(f"hooks.py file not found at {hooks_path}")
    
    # Create a backup of hooks.py
    backup_path = f"{hooks_path}.bak.{now().replace(':', '-').replace(' ', '_')}"
    try:
        with open(hooks_path, 'r') as src_file, open(backup_path, 'w') as backup_file:
            backup_file.write(src_file.read())
    except Exception as e:
        frappe.throw(f"Error creating backup of hooks.py: {str(e)}")
    
    # Read current hooks.py content
    try:
        with open(hooks_path, 'r') as file:
            hooks_content = file.read()
    except Exception as e:
        frappe.throw(f"Error reading hooks.py: {str(e)}")
    
    # Prepare fixtures list
    fixtures = []
    
    # Add DocTypes from export_doctypes
    if export_doc.get('export_doctypes'):
        doctype_names = [d['doctype_name'] for d in export_doc['export_doctypes'] if d.get('doctype_name')]
        fixtures.extend(doctype_names)
        
        # Add Custom Fields for these doctypes
        for dt in doctype_names:
            fixtures.append({
                "dt": "Custom Field",
                "filters": [["dt", "=", dt]]
            })
            
            # Add Property Setter for these doctypes
            fixtures.append({
                "dt": "Property Setter",
                "filters": [["doc_type", "=", dt]]
            })
    
    # Add Client Scripts
    if export_doc.get('all_client_scripts'):
        fixtures.append("Client Script")
    elif export_doc.get('export_client_scripts'):
        client_script_names = [c['client_script_name'] for c in export_doc['export_client_scripts'] if c.get('client_script_name')]
        if client_script_names:
            fixtures.append({
                "dt": "Client Script",
                "filters": [["name", "in", client_script_names]]
            })
    
    # Add Server Scripts
    if export_doc.get('all_server_scripts'):
        fixtures.append("Server Script")
    elif export_doc.get('export_server_scripts'):
        server_script_names = [s['server_script_name'] for s in export_doc['export_server_scripts'] if s.get('server_script_name')]
        if server_script_names:
            fixtures.append({
                "dt": "Server Script",
                "filters": [["name", "in", server_script_names]]
            })
    
    # Convert fixtures to Python format for hooks.py using a more reliable method
    fixtures_code = format_fixtures_for_hooks(fixtures)
    
    # Update hooks.py file
    try:
        # Check if hooks.py has existing fixtures
        if 'fixtures' in hooks_content:
            # Replace existing fixtures - using a more reliable approach
            pattern = re.compile(r'fixtures\s*=.*?(?=\n\w+|\Z)', re.DOTALL)
            if pattern.search(hooks_content):
                new_hooks_content = pattern.sub(f'fixtures = {fixtures_code}', hooks_content)
            else:
                # If pattern not found but 'fixtures' string exists, try another approach
                lines = hooks_content.split('\n')
                in_fixtures = False
                new_lines = []
                for line in lines:
                    if 'fixtures' in line and '=' in line and not in_fixtures:
                        new_lines.append(f'fixtures = {fixtures_code}')
                        in_fixtures = True
                    elif in_fixtures and (line.strip().startswith(']') or line.strip() == ']'):
                        in_fixtures = False
                    elif not in_fixtures:
                        new_lines.append(line)
                new_hooks_content = '\n'.join(new_lines)
        else:
            # Add fixtures to the end of the file
            if hooks_content.strip() and not hooks_content.endswith('\n'):
                hooks_content += '\n'
            new_hooks_content = hooks_content + f'\nfixtures = {fixtures_code}\n'
        
        # Ensure there are no indentation errors
        try:
            # Try to compile the new content to check for syntax errors
            compile(new_hooks_content, hooks_path, 'exec')
        except IndentationError:
            safe_log("Indentation error detected in generated hooks.py. Using simplified format.")
            # Fall back to a simpler format if there's an indentation issue
            new_hooks_content = hooks_content.split('fixtures =')[0].rstrip() + f'\n\nfixtures = {fixtures_code}\n'
        
        # Write updated hooks.py
        with open(hooks_path, 'w') as file:
            file.write(new_hooks_content)
        
        return True
    except Exception as e:
        # Restore from backup if update fails
        try:
            if os.path.exists(backup_path):
                with open(backup_path, 'r') as backup_file, open(hooks_path, 'w') as hooks_file:
                    hooks_file.write(backup_file.read())
        except:
            pass  # Ignore errors in restoring backup
        
        frappe.throw(f"Error updating hooks.py: {str(e)}")

def format_fixtures_for_hooks(fixtures):
    """Format fixtures list as Python code with proper indentation"""
    if not fixtures:
        return "[]"
    
    lines = ["["]
    for fixture in fixtures:
        if isinstance(fixture, str):
            lines.append(f'    "{fixture}",')
        elif isinstance(fixture, dict):
            lines.append("    {")
            for key, value in fixture.items():
                if isinstance(value, list):
                    lines.append(f'        "{key}": [')
                    for item in value:
                        if isinstance(item, list):
                            item_str = '['
                            for elem in item:
                                if isinstance(elem, str):
                                    item_str += f'"{elem}", '
                                else:
                                    item_str += f"{elem}, "
                            item_str = item_str.rstrip(", ") + "]"
                            lines.append(f"            {item_str},")
                        else:
                            lines.append(f'            "{item}",')
                    lines.append('        ],')
                else:
                    lines.append(f'        "{key}": "{value}",')
            lines.append("    },")
    lines.append("]")
    
    return "\n".join(lines)

def run_export_fixtures_with_timeout(app_info, timeout=300):
    """Run custom export fixtures logic and return exported file paths"""
    site_name = frappe.local.site
    bench_path = get_bench_path()
    fixtures_path = os.path.join(app_info["path"], app_info["name"], "fixtures")
    
    # Create fixtures directory if it doesn't exist
    os.makedirs(fixtures_path, exist_ok=True)
    
    try:
        # First approach: Get export_doc from the current execution context
        export_doc = None
        if hasattr(frappe.local, 'form_dict') and frappe.local.form_dict.get('kwargs'):
            try:
                kwargs = json.loads(frappe.local.form_dict.get('kwargs'))
                if kwargs.get('export_doc'):
                    export_doc = kwargs.get('export_doc')
            except:
                pass
        
        # If we have the export_doc, use our custom handler
        if export_doc:
            safe_log("Using custom export handler")
            return export_fixtures_handler(app_info, export_doc)
        
        # Otherwise, fall back to the bench command (not recommended)
        safe_log("Falling back to bench export-fixtures command")
        cmd = f"cd {bench_path} && bench --site {site_name} export-fixtures"
        
        # Use a safe logging approach
        safe_log("Running command: " + cmd)
        
        # Run process with timeout
        process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, preexec_fn=os.setsid)
        
        try:
            stdout, stderr = process.communicate(timeout=timeout)
            # Use safe logging for potentially long output
            if stdout:
                safe_log("Export fixtures stdout: " + stdout.decode('utf-8')[:500] + "..." if len(stdout) > 500 else stdout.decode('utf-8'))
        except subprocess.TimeoutExpired:
            # Kill the process group if it times out
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            safe_log(f"Process timed out after {timeout} seconds")
        
        # Find all exported JSON files
        exported_files = []
        for root, dirs, files in os.walk(fixtures_path):
            for file in files:
                if file.endswith('.json'):
                    file_path = os.path.join(root, file)
                    if os.path.getsize(file_path) > 2:  # More than just "{}"
                        exported_files.append(file_path)
        
        return exported_files
    
    except Exception as e:
        safe_log(f"Exception while running export fixtures: {str(e)}\n{frappe.get_traceback()}")
        frappe.throw(f"Error running export fixtures: {str(e)[:100]}")  # Limit error message length


def is_custom_doctype(doctype_name):
    """
    Determine if a DocType is a custom (user-created) DocType or a core DocType.
    
    Returns:
        bool: True if it's a custom DocType, False if it's a core DocType
    """
    try:
        # Get DocType metadata
        doctype_meta = frappe.get_doc("DocType", doctype_name)
        
        # Check if the DocType has the 'custom' flag set to 1
        if doctype_meta.custom == 1:
            return True
            
        # Check if the module is not a core module
        core_modules = [
            # Frappe core modules
            'Core', 'Website', 'Workflow', 'Email', 'Custom', 'Geo', 'Desk', 
            'Integrations', 'Printing', 'Contacts', 'Social', 'Automation',
            
            # ERPNext core modules
            'Accounts', 'CRM', 'Buying', 'Projects', 'Selling', 'Setup',
            'Manufacturing', 'Stock', 'Support', 'Utilities', 'Assets', 
            'Portal', 'Maintenance', 'Regional', 'ERPNext Integrations',
            'Quality Management', 'Communication', 'Telephony', 'Bulk Transaction',
            'Subcontracting', 'EDI',
            
            # HRMS core modules
            'HR', 'Payroll'
        ]
        
        # Not in core modules - it's a custom module
        if doctype_meta.module not in core_modules:
            return True
            
        # Check app name from module definition
        module_def = frappe.get_doc("Module Def", doctype_meta.module)
        if module_def.app_name not in ['frappe', 'erpnext', 'hrms']:
            return True
            
        # This is a core DocType
        return False
        
    except Exception as e:
        safe_log(f"Error checking if DocType {doctype_name} is custom: {str(e)}")
        # Default to treating as core DocType if we can't determine
        return False


def export_fixtures_handler(app_info, export_doc):
    """Central handler for exporting fixtures in the same format as bench export-fixtures"""
    fixtures_path = os.path.join(app_info["path"], app_info["name"], "fixtures")
    
    # Get hooks.py fixtures
    hooks_fixtures = []
    try:
        app_hooks = frappe.get_hooks(app_name=app_info["name"])
        if app_hooks and "fixtures" in app_hooks:
            hooks_fixtures = app_hooks["fixtures"]
            safe_log(f"Found {len(hooks_fixtures)} fixtures in hooks")
    except:
        pass
    
    # Run export commands manually to ensure we get good data
    exported_files = []
    
    # 1. Export DocTypes from export_doc
    for dt_entry in export_doc.get('export_doctypes', []):
        if dt_entry.get('doctype_name'):
            doctype = dt_entry.get('doctype_name')
            
            # Check if this is a custom DocType
            is_custom = is_custom_doctype(doctype)
            
            # For custom DocTypes, export the full DocType definition
            if is_custom:
                safe_log(f"DocType {doctype} is a custom DocType - exporting definition")
                file_path = export_doctype_definition(doctype, fixtures_path)
                if file_path:
                    exported_files.append(file_path)
                
                # Also export the data records for reference - exactly like bench export-fixtures
                data_file_path = export_doctype(doctype, fixtures_path)
                if data_file_path and data_file_path not in exported_files:
                    exported_files.append(data_file_path)
            
            # Export Custom Fields for all DocTypes
            cf_path = export_custom_fields(doctype, fixtures_path)
            if cf_path and cf_path not in exported_files:
                exported_files.append(cf_path)
            
            # Export Property Setters for all DocTypes
            ps_path = export_property_setters(doctype, fixtures_path)
            if ps_path and ps_path not in exported_files:
                exported_files.append(ps_path)
    
    # 2. Export Client Scripts
    if export_doc.get('all_client_scripts'):
        file_path = export_client_scripts(None, fixtures_path)
        if file_path and file_path not in exported_files:
            exported_files.append(file_path)
    elif export_doc.get('export_client_scripts'):
        client_script_names = [c['client_script_name'] for c in export_doc['export_client_scripts'] if c.get('client_script_name')]
        if client_script_names:
            filters = [["name", "in", client_script_names]]
            file_path = export_client_scripts(filters, fixtures_path)
            if file_path and file_path not in exported_files:
                exported_files.append(file_path)
    
    # 3. Export Server Scripts
    if export_doc.get('all_server_scripts'):
        file_path = export_server_scripts(None, fixtures_path)
        if file_path and file_path not in exported_files:
            exported_files.append(file_path)
    elif export_doc.get('export_server_scripts'):
        server_script_names = [s['server_script_name'] for s in export_doc['export_server_scripts'] if s.get('server_script_name')]
        if server_script_names:
            filters = [["name", "in", server_script_names]]
            file_path = export_server_scripts(filters, fixtures_path)
            if file_path and file_path not in exported_files:
                exported_files.append(file_path)
    
    # 4. Find any additional JSON files
    for root, dirs, files in os.walk(fixtures_path):
        for file in files:
            if file.endswith('.json'):
                file_path = os.path.join(root, file)
                if file_path not in exported_files and os.path.getsize(file_path) > 2:
                    exported_files.append(file_path)
    
    return exported_files



def export_doctype(doctype, fixtures_path):
    """Export a DocType to fixtures"""
    try:
        file_name = doctype.lower().replace(" ", "_") + ".json"
        file_path = os.path.join(fixtures_path, file_name)
        
        # Get the metadata for the doctype to properly structure the export
        doctype_meta = frappe.get_meta(doctype)
        if not doctype_meta:
            safe_log(f"DocType {doctype} metadata not found")
            return None
        
        # Get all records of this DocType
        docs = frappe.get_all(doctype, fields=["name"])
        
        if not docs:
            # If there are no records, log and return
            safe_log(f"No records found for DocType {doctype}")
            return None
        
        data = []
        for doc in docs:
            try:
                # Load the doc more carefully, with explicit field selection
                full_doc = frappe.get_doc(doctype, doc.name)
                doc_data = {}
                
                # Add each field manually to avoid serialization issues
                for field in doctype_meta.fields:
                    field_name = field.fieldname
                    if hasattr(full_doc, field_name):
                        field_value = getattr(full_doc, field_name)
                        
                        # Special handling for date and datetime fields
                        if field.fieldtype in ['Date', 'Datetime'] and field_value:
                            try:
                                # Convert to string in ISO format for dates
                                if isinstance(field_value, str):
                                    # Already a string, leave as is
                                    doc_data[field_name] = field_value
                                else:
                                    # Convert date/datetime to string
                                    doc_data[field_name] = field_value.isoformat()
                            except:
                                # If conversion fails, use string representation
                                doc_data[field_name] = str(field_value)
                        else:
                            # For other field types
                            doc_data[field_name] = field_value
                
                # Ensure doctype is set correctly
                doc_data['doctype'] = doctype
                
                # Include essential fields
                doc_data['name'] = full_doc.name
                
                # Clean up doc_data by removing unnecessary fields
                for field in ["creation", "modified", "modified_by", "owner", "docstatus", "parentfield", "parenttype"]:
                    if field in doc_data:
                        del doc_data[field]
                
                data.append(doc_data)
            except Exception as doc_error:
                safe_log(f"Error exporting {doctype} {doc.name}: {str(doc_error)}")
        
        if data:
            # Write data more carefully
            try:
                # Better JSON handling
                json_str = json.dumps(data, indent=4, default=str, ensure_ascii=False)
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(json_str)
                
                safe_log(f"Exported {len(data)} {doctype} records to {file_path}")
                return file_path
            except Exception as write_error:
                safe_log(f"Error writing {doctype} to file: {str(write_error)}")
    
    except Exception as e:
        safe_log(f"Error exporting DocType {doctype}: {str(e)}")
    
    return None


def export_doctype_definition(doctype, fixtures_path):
    """
    Export the DocType structure in the same format as bench export-fixtures
    """
    try:
        # Standard bench export uses this filename format
        file_name = f"{doctype.lower().replace(' ', '_')}.json"
        file_path = os.path.join(fixtures_path, file_name)
        
        # Get the DocType document
        doctype_doc = frappe.get_doc("DocType", doctype)
        if not doctype_doc:
            safe_log(f"DocType {doctype} not found")
            return None
        
        # Get all fields (docfields) for this DocType
        fields = frappe.get_all("DocField", 
                              filters={"parent": doctype},
                              fields=["*"])
        
        # Prepare the DocType export - as_dict() gets all fields
        export_data = doctype_doc.as_dict()
        
        # Remove unnecessary fields but keep the ones needed by bench import
        system_fields = ["creation", "modified", "modified_by", "owner", "docstatus"]
        for field in system_fields:
            if field in export_data:
                del export_data[field]
        
        # Add fields to the DocType definition - replace any existing fields array
        export_data["fields"] = []
        for field in fields:
            field_data = {}
            for key, value in field.items():
                # Skip unnecessary fields
                if key in system_fields + ["parent", "parentfield", "parenttype"]:
                    continue
                field_data[key] = value
            export_data["fields"].append(field_data)
        
        # Get permissions for this DocType
        permissions = frappe.get_all("DocPerm", 
                                   filters={"parent": doctype},
                                   fields=["*"])
        
        # Add permissions to the DocType definition
        export_data["permissions"] = []
        for perm in permissions:
            perm_data = {}
            for key, value in perm.items():
                # Skip unnecessary fields
                if key in system_fields + ["parent", "parentfield", "parenttype"]:
                    continue
                perm_data[key] = value
            export_data["permissions"].append(perm_data)
        
        # Make sure the doctype field is correct for bench import
        export_data["doctype"] = "DocType"
        
        # Write to file - bench export puts one DocType per file in an array
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump([export_data], f, indent=4, default=str, ensure_ascii=False)
        
        safe_log(f"Exported DocType definition for {doctype} to {file_path}")
        return file_path
    
    except Exception as e:
        safe_log(f"Error exporting DocType definition for {doctype}: {str(e)}\n{frappe.get_traceback()}")
        return None
    
def export_doctype_with_filters(doctype, filters, fixtures_path):
    """Export a DocType with filters to fixtures"""
    try:
        file_name = doctype.lower().replace(" ", "_") + ".json"
        file_path = os.path.join(fixtures_path, file_name)
        
        # Convert filters format if needed
        filter_dict = {}
        if isinstance(filters, list):
            for f in filters:
                if len(f) >= 3:
                    filter_dict[f[0]] = f[2]
        
        # Get filtered records
        docs = frappe.get_all(doctype, filters=filter_dict or filters, fields=["name"])
        
        if not docs:
            safe_log(f"No records found for DocType {doctype} with filters {filters}")
            return None
        
        # Get the metadata for the doctype
        doctype_meta = frappe.get_meta(doctype)
        
        data = []
        for doc in docs:
            try:
                # Load the doc more carefully
                full_doc = frappe.get_doc(doctype, doc.name)
                doc_data = {}
                
                # Add each field manually to avoid serialization issues
                for field in doctype_meta.fields:
                    field_name = field.fieldname
                    if hasattr(full_doc, field_name):
                        field_value = getattr(full_doc, field_name)
                        
                        # Special handling for date and datetime fields
                        if field.fieldtype in ['Date', 'Datetime'] and field_value:
                            try:
                                if isinstance(field_value, str):
                                    doc_data[field_name] = field_value
                                else:
                                    doc_data[field_name] = field_value.isoformat()
                            except:
                                doc_data[field_name] = str(field_value)
                        else:
                            doc_data[field_name] = field_value
                
                # Ensure doctype is set correctly
                doc_data['doctype'] = doctype
                
                # Include essential fields
                doc_data['name'] = full_doc.name
                
                # Clean up doc_data
                for field in ["creation", "modified", "modified_by", "owner", "docstatus", "parentfield", "parenttype"]:
                    if field in doc_data:
                        del doc_data[field]
                
                data.append(doc_data)
            except Exception as doc_error:
                safe_log(f"Error exporting {doctype} {doc.name}: {str(doc_error)}")
        
        if data:
            # Write data more carefully
            try:
                json_str = json.dumps(data, indent=4, default=str, ensure_ascii=False)
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(json_str)
                
                safe_log(f"Exported {len(data)} {doctype} records with filters to {file_path}")
                return file_path
            except Exception as write_error:
                safe_log(f"Error writing filtered {doctype} to file: {str(write_error)}")
    
    except Exception as e:
        safe_log(f"Error exporting DocType {doctype} with filters: {str(e)}")
    
    return None

def export_custom_fields(doctype, fixtures_path):
    """Export Custom Fields for a DocType"""
    try:
        file_name = "custom_field.json"
        file_path = os.path.join(fixtures_path, file_name)
        
        # Get custom fields for this DocType
        custom_fields = frappe.get_all("Custom Field", 
                                      filters={"dt": doctype}, 
                                      fields=["*"])  # Get all fields directly
        
        if not custom_fields:
            # Try alternative approach - get custom fields by directly querying
            try:
                # Direct SQL query as a fallback
                custom_fields = frappe.db.sql("""
                    SELECT * FROM `tabCustom Field` 
                    WHERE dt = %s
                """, (doctype,), as_dict=1)
                
                safe_log(f"Retrieved {len(custom_fields)} custom fields via SQL for {doctype}")
            except Exception as sql_error:
                safe_log(f"SQL query error for Custom Field: {str(sql_error)}")
        
        if not custom_fields:
            safe_log(f"No custom fields found for {doctype}")
            # Create a minimal placeholder entry
            custom_fields = [{
                "doctype": "Custom Field",
                "dt": doctype,
                "fieldname": "_placeholder",
                "label": "Placeholder",
                "fieldtype": "Data",
                "__export_placeholder": True  # Mark as placeholder
            }]
        
        # Check if file exists and read existing data
        existing_data = []
        if os.path.exists(file_path) and os.path.getsize(file_path) > 2:
            try:
                with open(file_path, 'r') as f:
                    existing_data = json.load(f)
                    if not isinstance(existing_data, list):
                        existing_data = []
            except:
                existing_data = []
        
        # Get custom field data
        new_data = []
        for cf in custom_fields:
            try:
                # If cf is already a dict from SQL query, use it directly
                if isinstance(cf, dict) and cf.get("name"):
                    cf_data = cf
                else:
                    # Otherwise get the full doc
                    cf_data = frappe.get_doc("Custom Field", cf.name).as_dict()
                
                # Clean up data
                for field in ["creation", "modified", "modified_by", "owner", "docstatus", "parentfield", "parenttype"]:
                    if field in cf_data:
                        del cf_data[field]
                
                new_data.append(cf_data)
            except Exception as cf_error:
                safe_log(f"Error exporting Custom Field for {doctype}: {str(cf_error)}")
        
        if new_data:
            # Merge with existing data, avoiding duplicates
            all_data = existing_data.copy() if existing_data else []
            
            # Get existing dt/fieldname combinations
            existing_keys = set()
            for item in all_data:
                if item.get("dt") and item.get("fieldname"):
                    existing_keys.add((item.get("dt"), item.get("fieldname")))
            
            # Add new items avoiding duplicates
            for item in new_data:
                key = (item.get("dt"), item.get("fieldname"))
                if key not in existing_keys:
                    all_data.append(item)
                    existing_keys.add(key)
            
            # Remove placeholder entries if we have real data
            if len(all_data) > 1:
                all_data = [item for item in all_data if not item.get("__export_placeholder")]
            
            with open(file_path, 'w') as f:
                json.dump(all_data, f, indent=4)
            
            safe_log(f"Exported {len(new_data)} Custom Fields for {doctype} to {file_path}")
            return file_path
    
    except Exception as e:
        safe_log(f"Error exporting Custom Fields for {doctype}: {str(e)}")
    
    return None

def export_custom_fields_with_filters(filters, fixtures_path):
    """Export Custom Fields with filters"""
    try:
        file_name = "custom_field.json"
        file_path = os.path.join(fixtures_path, file_name)
        
        # Convert filters format if needed
        filter_dict = {}
        if isinstance(filters, list):
            for f in filters:
                if len(f) >= 3:
                    filter_dict[f[0]] = f[2]
        
        # Get filtered custom fields
        custom_fields = frappe.get_all("Custom Field", filters=filter_dict or filters, fields=["*"])
        
        if not custom_fields:
            safe_log(f"No custom fields found with filters {filters}")
            return None
        
        # Check if file exists and read existing data
        existing_data = []
        if os.path.exists(file_path) and os.path.getsize(file_path) > 2:
            try:
                with open(file_path, 'r') as f:
                    existing_data = json.load(f)
                    if not isinstance(existing_data, list):
                        existing_data = []
            except:
                existing_data = []
        
        # Process custom field data
        new_data = []
        for cf in custom_fields:
            try:
                # If cf already has all fields, use it directly
                if isinstance(cf, dict) and cf.get("name") and cf.get("dt") and cf.get("fieldname"):
                    cf_data = cf
                else:
                    # Otherwise get the full doc
                    cf_data = frappe.get_doc("Custom Field", cf.name).as_dict()
                
                # Clean up data
                for field in ["creation", "modified", "modified_by", "owner", "docstatus", "parentfield", "parenttype"]:
                    if field in cf_data:
                        del cf_data[field]
                
                new_data.append(cf_data)
            except Exception as cf_error:
                safe_log(f"Error exporting Custom Field with filters: {str(cf_error)}")
        
        if new_data:
            # Merge with existing data, avoiding duplicates
            all_data = existing_data.copy() if existing_data else []
            
            # Get existing dt/fieldname combinations
            existing_keys = set()
            for item in all_data:
                if item.get("dt") and item.get("fieldname"):
                    existing_keys.add((item.get("dt"), item.get("fieldname")))
            
            # Add new items avoiding duplicates
            for item in new_data:
                key = (item.get("dt"), item.get("fieldname"))
                if key not in existing_keys:
                    all_data.append(item)
                    existing_keys.add(key)
            
            with open(file_path, 'w') as f:
                json.dump(all_data, f, indent=4)
            
            safe_log(f"Exported {len(new_data)} Custom Fields with filters to {file_path}")
            return file_path
    
    except Exception as e:
        safe_log(f"Error exporting Custom Fields with filters: {str(e)}")
    
    return None

def export_property_setters(doctype, fixtures_path):
    """Export Property Setters for a DocType"""
    try:
        file_name = "property_setter.json"
        file_path = os.path.join(fixtures_path, file_name)
        
        # Get property setters for this DocType
        property_setters = frappe.get_all("Property Setter", 
                                         filters={"doc_type": doctype}, 
                                         fields=["*"])  # Get all fields directly
        
        if not property_setters:
            # Try alternative approach - get property setters by directly querying
            try:
                # Direct SQL query as a fallback
                property_setters = frappe.db.sql("""
                    SELECT * FROM `tabProperty Setter` 
                    WHERE doc_type = %s
                """, (doctype,), as_dict=1)
                
                safe_log(f"Retrieved {len(property_setters)} property setters via SQL for {doctype}")
            except Exception as sql_error:
                safe_log(f"SQL query error for Property Setter: {str(sql_error)}")
        
        if not property_setters:
            safe_log(f"No property setters found for {doctype}")
            # Create a minimal placeholder entry
            property_setters = [{
                "doctype": "Property Setter",
                "doc_type": doctype,
                "property": "_placeholder",
                "value": "This is a placeholder for Property Setter export",
                "property_type": "Data",
                "__export_placeholder": True  # Mark as placeholder
            }]
        
        # Check if file exists and read existing data
        existing_data = []
        if os.path.exists(file_path) and os.path.getsize(file_path) > 2:
            try:
                with open(file_path, 'r') as f:
                    existing_data = json.load(f)
                    if not isinstance(existing_data, list):
                        existing_data = []
            except:
                existing_data = []
        
        # Get property setter data
        new_data = []
        for ps in property_setters:
            try:
                # If ps is already a dict from SQL query, use it directly
                if isinstance(ps, dict) and ps.get("name"):
                    ps_data = ps
                else:
                    # Otherwise get the full doc
                    ps_data = frappe.get_doc("Property Setter", ps.name).as_dict()
                
                # Clean up data
                for field in ["creation", "modified", "modified_by", "owner", "docstatus", "parentfield", "parenttype"]:
                    if field in ps_data:
                        del ps_data[field]
                
                new_data.append(ps_data)
            except Exception as ps_error:
                safe_log(f"Error exporting Property Setter for {doctype}: {str(ps_error)}")
        
        if new_data:
            # Merge with existing data, avoiding duplicates
            all_data = existing_data.copy() if existing_data else []
            
            # Get existing doc_type/property combinations
            existing_keys = set()
            for item in all_data:
                if item.get("doc_type") and item.get("property"):
                    existing_keys.add((item.get("doc_type"), item.get("property")))
            
            # Add new items avoiding duplicates
            for item in new_data:
                key = (item.get("doc_type"), item.get("property"))
                if key not in existing_keys:
                    all_data.append(item)
                    existing_keys.add(key)
            
            # Remove placeholder entries if we have real data
            if len(all_data) > 1:
                all_data = [item for item in all_data if not item.get("__export_placeholder")]
            
            with open(file_path, 'w') as f:
                json.dump(all_data, f, indent=4)
            
            safe_log(f"Exported {len(new_data)} Property Setters for {doctype} to {file_path}")
            return file_path
    
    except Exception as e:
        safe_log(f"Error exporting Property Setters for {doctype}: {str(e)}")
    
    return None

def export_property_setters_with_filters(filters, fixtures_path):
    """Export Property Setters with filters"""
    try:
        file_name = "property_setter.json"
        file_path = os.path.join(fixtures_path, file_name)
        
        # Convert filters format if needed
        filter_dict = {}
        if isinstance(filters, list):
            for f in filters:
                if len(f) >= 3:
                    filter_dict[f[0]] = f[2]
        
        # Get filtered property setters
        property_setters = frappe.get_all("Property Setter", filters=filter_dict or filters, fields=["*"])
        
        if not property_setters:
            safe_log(f"No property setters found with filters {filters}")
            return None
        
        # Check if file exists and read existing data
        existing_data = []
        if os.path.exists(file_path) and os.path.getsize(file_path) > 2:
            try:
                with open(file_path, 'r') as f:
                    existing_data = json.load(f)
                    if not isinstance(existing_data, list):
                        existing_data = []
            except:
                existing_data = []
        
        # Process property setter data
        new_data = []
        for ps in property_setters:
            try:
                # If ps already has all fields, use it directly
                if isinstance(ps, dict) and ps.get("name") and ps.get("doc_type") and ps.get("property"):
                    ps_data = ps
                else:
                    # Otherwise get the full doc
                    ps_data = frappe.get_doc("Property Setter", ps.name).as_dict()
                
                # Clean up data
                for field in ["creation", "modified", "modified_by", "owner", "docstatus", "parentfield", "parenttype"]:
                    if field in ps_data:
                        del ps_data[field]
                
                new_data.append(ps_data)
            except Exception as ps_error:
                safe_log(f"Error exporting Property Setter with filters: {str(ps_error)}")
        
        if new_data:
            # Merge with existing data, avoiding duplicates
            all_data = existing_data.copy() if existing_data else []
            
            # Get existing doc_type/property combinations
            existing_keys = set()
            for item in all_data:
                if item.get("doc_type") and item.get("property"):
                    existing_keys.add((item.get("doc_type"), item.get("property")))
            
            # Add new items avoiding duplicates
            for item in new_data:
                key = (item.get("doc_type"), item.get("property"))
                if key not in existing_keys:
                    all_data.append(item)
                    existing_keys.add(key)
            
            with open(file_path, 'w') as f:
                json.dump(all_data, f, indent=4)
            
            safe_log(f"Exported {len(new_data)} Property Setters with filters to {file_path}")
            return file_path
    
    except Exception as e:
        safe_log(f"Error exporting Property Setters with filters: {str(e)}")
    
    return None

def export_client_scripts(filters, fixtures_path):
    """Export Client Scripts with filters"""
    try:
        file_name = "client_script.json"
        file_path = os.path.join(fixtures_path, file_name)
        
        # Determine if we're exporting all client scripts or specific ones
        if not filters:
            # Export all client scripts
            client_scripts = frappe.get_all("Client Script", fields=["*"])
        else:
            # Convert filters format if needed
            filter_dict = {}
            if isinstance(filters, list):
                for f in filters:
                    if len(f) >= 3:
                        filter_dict[f[0]] = f[2]
            
            # Get filtered client scripts
            client_scripts = frappe.get_all("Client Script", filters=filter_dict or filters, fields=["*"])
        
        if not client_scripts:
            safe_log("No client scripts found")
            return None
        
        # Check if file exists and read existing data
        existing_data = []
        if os.path.exists(file_path) and os.path.getsize(file_path) > 2:
            try:
                with open(file_path, 'r') as f:
                    existing_data = json.load(f)
                    if not isinstance(existing_data, list):
                        existing_data = []
            except:
                existing_data = []
        
        data = []
        for cs in client_scripts:
            try:
                # If cs already has all fields, use it directly
                if isinstance(cs, dict) and cs.get("name") and cs.get("dt") and cs.get("script"):
                    cs_data = cs
                else:
                    # Otherwise get the full doc
                    cs_data = frappe.get_doc("Client Script", cs.name).as_dict()
                
                # Clean up data
                for field in ["creation", "modified", "modified_by", "owner", "docstatus", "parentfield", "parenttype"]:
                    if field in cs_data:
                        del cs_data[field]
                
                data.append(cs_data)
            except Exception as cs_error:
                safe_log(f"Error exporting Client Script: {str(cs_error)}")
        
        if data:
            # Merge with existing data, avoiding duplicates
            all_data = existing_data.copy() if existing_data else []
            
            # Get existing dt/name combinations
            existing_keys = set()
            for item in all_data:
                if item.get("dt") and item.get("name"):
                    existing_keys.add((item.get("dt"), item.get("name")))
            
            # Add new items avoiding duplicates
            for item in data:
                key = (item.get("dt"), item.get("name"))
                if key not in existing_keys:
                    all_data.append(item)
                    existing_keys.add(key)
            
            with open(file_path, 'w') as f:
                json.dump(all_data, f, indent=4)
            
            safe_log(f"Exported {len(data)} Client Scripts to {file_path}")
            return file_path
    
    except Exception as e:
        safe_log(f"Error exporting Client Scripts: {str(e)}")
    
    return None

def export_server_scripts(filters, fixtures_path):
    """Export Server Scripts with filters"""
    try:
        file_name = "server_script.json"
        file_path = os.path.join(fixtures_path, file_name)
        
        # Determine if we're exporting all server scripts or specific ones
        if not filters:
            # Export all server scripts
            server_scripts = frappe.get_all("Server Script", fields=["*"])
        else:
            # Convert filters format if needed
            filter_dict = {}
            if isinstance(filters, list):
                for f in filters:
                    if len(f) >= 3:
                        filter_dict[f[0]] = f[2]
            
            # Get filtered server scripts
            server_scripts = frappe.get_all("Server Script", filters=filter_dict or filters, fields=["*"])
        
        if not server_scripts:
            safe_log("No server scripts found")
            return None
        
        # Check if file exists and read existing data
        existing_data = []
        if os.path.exists(file_path) and os.path.getsize(file_path) > 2:
            try:
                with open(file_path, 'r') as f:
                    existing_data = json.load(f)
                    if not isinstance(existing_data, list):
                        existing_data = []
            except:
                existing_data = []
        
        data = []
        for ss in server_scripts:
            try:
                # If ss already has all fields, use it directly
                if isinstance(ss, dict) and ss.get("name") and ss.get("script_type") and ss.get("script"):
                    ss_data = ss
                else:
                    # Otherwise get the full doc
                    ss_data = frappe.get_doc("Server Script", ss.name).as_dict()
                
                # Clean up data
                for field in ["creation", "modified", "modified_by", "owner", "docstatus", "parentfield", "parenttype"]:
                    if field in ss_data:
                        del ss_data[field]
                
                data.append(ss_data)
            except Exception as ss_error:
                safe_log(f"Error exporting Server Script: {str(ss_error)}")
        
        if data:
            # Merge with existing data, avoiding duplicates
            all_data = existing_data.copy() if existing_data else []
            
            # Get existing name values
            existing_keys = set()
            for item in all_data:
                if item.get("name"):
                    existing_keys.add(item.get("name"))
            
            # Add new items avoiding duplicates
            for item in data:
                key = item.get("name")
                if key not in existing_keys:
                    all_data.append(item)
                    existing_keys.add(key)
            
            with open(file_path, 'w') as f:
                json.dump(all_data, f, indent=4)
            
            safe_log(f"Exported {len(data)} Server Scripts to {file_path}")
            return file_path
    
    except Exception as e:
        safe_log(f"Error exporting Server Scripts: {str(e)}")
    
    return None

def fix_empty_json_files(app_info, export_doc):
    """Fix any empty JSON files by forcing a direct export"""
    try:
        fixtures_path = os.path.join(app_info["path"], app_info["name"], "fixtures")
        
        # Check for empty or corrupted JSON files
        empty_files = []
        for root, dirs, files in os.walk(fixtures_path):
            for file in files:
                if file.endswith('.json'):
                    file_path = os.path.join(root, file)
                    # File is empty or just contains "{}"
                    if os.path.getsize(file_path) <= 5:
                        empty_files.append((file_path, file.replace('.json', '')))
                    else:
                        # Check if file is valid JSON
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                                if not content.strip() or content.strip() in ['{}', '[]']:
                                    empty_files.append((file_path, file.replace('.json', '')))
                                else:
                                    # Try to parse it
                                    json.loads(content)
                        except:
                            # If we can't parse it, consider it corrupted
                            empty_files.append((file_path, file.replace('.json', '')))
        
        safe_log(f"Found {len(empty_files)} empty/corrupted JSON files")
        
        # Fix empty/corrupted files
        for file_path, file_name in empty_files:
            # Try to determine what kind of file this is
            if file_name == "custom_field":
                # Force export of all Custom Fields for all DocTypes
                if export_doc.get('export_doctypes'):
                    for dt_entry in export_doc['export_doctypes']:
                        if dt_entry.get('doctype_name'):
                            try:
                                export_custom_fields(dt_entry['doctype_name'], fixtures_path)
                            except Exception as e:
                                safe_log(f"Error fixing custom_field.json: {str(e)}")
            
            elif file_name == "property_setter":
                # Force export of all Property Setters for all DocTypes
                if export_doc.get('export_doctypes'):
                    for dt_entry in export_doc['export_doctypes']:
                        if dt_entry.get('doctype_name'):
                            try:
                                export_property_setters(dt_entry['doctype_name'], fixtures_path)
                            except Exception as e:
                                safe_log(f"Error fixing property_setter.json: {str(e)}")
            
            elif file_name == "client_script":
                # Force export of Client Scripts
                try:
                    export_client_scripts(None, fixtures_path)
                except Exception as e:
                    safe_log(f"Error fixing client_script.json: {str(e)}")
            
            elif file_name == "server_script":
                # Force export of Server Scripts
                try:
                    export_server_scripts(None, fixtures_path)
                except Exception as e:
                    safe_log(f"Error fixing server_script.json: {str(e)}")
            
            else:
                # This might be a DocType - try direct export
                try:
                    # Try different case formats: snake_case, Title Case, etc.
                    possible_doctypes = [
                        file_name,  # as is
                        file_name.replace('_', ' ').title(),  # snake_case to Title Case
                        file_name.title()  # lowercase to Title Case
                    ]
                    
                    for doctype in possible_doctypes:
                        if frappe.db.exists("DocType", doctype):
                            try:
                                # Found a matching DocType, export it
                                export_doctype(doctype, fixtures_path)
                                break
                            except Exception as dt_error:
                                safe_log(f"Error fixing {file_name}.json: {str(dt_error)}")
                except Exception as e:
                    safe_log(f"Error determining DocType for {file_name}: {str(e)}")
    
    except Exception as e:
        safe_log(f"Error in fix_empty_json_files: {str(e)}")

def save_exported_files(exported_files, doctype_name):
    """Save exported JSON files to File DocType and return file links"""
    file_links = []
    
    if not exported_files:
        frappe.msgprint("No fixture files were exported.")
        return file_links
    
    timestamp = now().replace(':', '-').replace(' ', '_')
    zip_filename = f"customizations_export_{timestamp}.zip"
    
    try:
        import zipfile
        from io import BytesIO
        
        # Create a zip file in memory
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Track filenames to avoid duplicates in ZIP
            added_files = set()
            
            for file_path in exported_files:
                file_name = os.path.basename(file_path)
                
                # Check for duplicate filenames - add a counter if needed
                base_name = file_name
                counter = 1
                while file_name in added_files:
                    name_parts = base_name.rsplit('.', 1)
                    if len(name_parts) > 1:
                        file_name = f"{name_parts[0]}_{counter}.{name_parts[1]}"
                    else:
                        file_name = f"{base_name}_{counter}"
                    counter += 1
                
                added_files.add(file_name)
                
                with open(file_path, 'rb') as f:
                    file_content = f.read()
                    zip_file.writestr(file_name, file_content)
                
                # Skip saving individual file if it already exists in File DocType
                existing_file = frappe.get_all("File", 
                                             filters={
                                                 "file_name": file_name,
                                                 "attached_to_doctype": "Export Customizations Module",
                                                 "attached_to_name": doctype_name
                                             },
                                             fields=["name", "file_url"])
                
                if existing_file:
                    file_links.append({
                        "name": existing_file[0].name,
                        "file_name": file_name,
                        "file_url": existing_file[0].file_url
                    })
                    continue
                
                # Save individual JSON file
                try:
                    file_doc = save_file(
                        fname=file_name,
                        content=file_content,
                        dt="Export Customizations Module",
                        dn=doctype_name,
                        folder="Home/Attachments",
                        is_private=1
                    )
                    
                    file_links.append({
                        "name": file_doc.name,
                        "file_name": file_doc.file_name,
                        "file_url": file_doc.file_url
                    })
                except Exception as file_error:
                    safe_log(f"Error saving individual file {file_name}: {str(file_error)}")
        
        # Check if zip already exists
        existing_zip = frappe.get_all("File", 
                                     filters={
                                         "file_name": zip_filename,
                                         "attached_to_doctype": "Export Customizations Module",
                                         "attached_to_name": doctype_name
                                     },
                                     fields=["name", "file_url"])
        
        if existing_zip:
            # Delete existing zip to avoid accumulation
            try:
                frappe.delete_doc("File", existing_zip[0].name)
                frappe.db.commit()
                safe_log(f"Deleted existing ZIP file {existing_zip[0].name}")
            except Exception as del_error:
                safe_log(f"Error deleting existing ZIP: {str(del_error)}")
        
        # Save the zip file
        zip_buffer.seek(0)
        zip_file_doc = save_file(
            fname=zip_filename,
            content=zip_buffer.getvalue(),
            dt="Export Customizations Module",
            dn=doctype_name,
            folder="Home/Attachments",
            is_private=1
        )
        
        file_links.append({
            "name": zip_file_doc.name,
            "file_name": zip_file_doc.file_name,
            "file_url": zip_file_doc.file_url,
            "is_zip": True
        })
        
        frappe.db.commit()
        
    except Exception as e:
        safe_log(f"Error saving exported files: {str(e)}")
        frappe.msgprint(f"Error creating zip file: {str(e)}")
        
        # If zip fails, at least try to save individual files
        for file_path in exported_files:
            try:
                file_name = os.path.basename(file_path)
                with open(file_path, 'rb') as f:
                    file_content = f.read()
                
                file_doc = save_file(
                    fname=file_name,
                    content=file_content,
                    dt="Export Customizations Module",
                    dn=doctype_name,
                    folder="Home/Attachments",
                    is_private=1
                )
                
                file_links.append({
                    "name": file_doc.name,
                    "file_name": file_doc.file_name,
                    "file_url": file_doc.file_url
                })
            except Exception as inner_e:
                safe_log(f"Error saving file {file_path}: {str(inner_e)}")
    
    return file_links

def send_exported_files_email(emails, file_links, doctype_name):
    """Send email with exported files as attachments"""
    email_list = [email['email'] for email in emails if email.get('email')]
    
    if not email_list:
        return False
    
    # Prepare attachments
    attachments = []
    
    # Prefer the zip file if it exists
    zip_file = next((f for f in file_links if f.get('is_zip')), None)
    
    if zip_file:
        # Only attach the zip file to avoid large emails
        file_doc = frappe.get_doc("File", zip_file['name'])
        if file_doc and file_doc.file_url:
            attachments.append({
                "fname": file_doc.file_name,
                "fcontent": file_doc.get_content()
            })
    else:
        # If no zip file, attach individual files (up to a reasonable limit)
        for i, file_link in enumerate(file_links[:10]):  # Limit to 10 files
            file_doc = frappe.get_doc("File", file_link['name'])
            if file_doc and file_doc.file_url:
                attachments.append({
                    "fname": file_doc.file_name,
                    "fcontent": file_doc.get_content()
                })
    
    # Send email
    subject = f"ERPNext Customizations Export - {doctype_name}"
    message = f"""
    <p>Hello,</p>
    <p>Please find attached the exported customizations from ERPNext.</p>
    <p>The following files have been exported:</p>
    <ul>
        {''.join([f'<li>{file_link["file_name"]}</li>' for file_link in file_links])}
    </ul>
    <p>Regards,<br>ERPNext System</p>
    """
    
    try:
        frappe.sendmail(
            recipients=email_list,
            subject=subject,
            message=message,
            attachments=attachments
        )
        return True
    except Exception as e:
        safe_log(f"Error sending email: {str(e)}")
        return False

@frappe.whitelist()
def get_export_status(doctype_name):
    """Get the current status of an export job"""
    try:
        doc = frappe.get_doc("Export Customizations Module", doctype_name)
        status = {
            "export_status": doc.get("export_status", "Not Started"),
            "export_message": doc.get("export_message", ""),
            "last_export_update": doc.get("last_export_update", ""),
            "completed": doc.get("export_status") in ["Completed", "Completed with warnings", "Failed"]
        }
        
        # If completed, get the file links
        if status["completed"] and doc.get("last_export_result"):
            try:
                result = json.loads(doc.get("last_export_result"))
                status["files"] = result.get("files", [])
            except:
                status["files"] = []
        
        return status
    except Exception as e:
        safe_log(f"Error getting export status: {str(e)}")
        return {
            "export_status": "Error",
            "export_message": f"Error getting status: {str(e)}",
            "completed": True
        }

def safe_log(message, title="Export Fixtures"):
    """Log a message safely, ensuring it doesn't exceed character limits"""
    try:
        # Limit title length
        if len(title) > 100:
            title = title[:97] + "..."
        
        # Limit message length for the log title field
        short_message = message
        if len(short_message) > 100:
            short_message = short_message[:97] + "..."
        
        # Use frappe db directly to avoid validation issues
        error_log = frappe.new_doc("Error Log")
        error_log.error = message
        error_log.method = frappe.utils.get_current_site() + " | " + title
        error_log.title = short_message
        
        # Insert directly with db_insert to bypass validation
        error_log.db_insert()
        frappe.db.commit()
    except Exception as e:
        # If even this fails, print to console as last resort
        print(f"ERROR LOGGING FAILED: {str(e)}")
        print(f"Original message: {message[:200]}...")