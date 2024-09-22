import gspread
from google.oauth2.service_account import Credentials
from flask import Flask, render_template, session,request, redirect, url_for, flash, jsonify
import random
import string
from datetime import datetime
import datetime
import pandas as pd
from flask import send_file
import io
from datetime import datetime
from collections import defaultdict


# Define the scope and create credentials
scopes = ["https://www.googleapis.com/auth/spreadsheets"]
creds = Credentials.from_service_account_file("credentials.json", scopes=scopes)

# Authorize the client
client = gspread.authorize(creds)

# Spreadsheet IDs
INVENTORY_SHEET_ID = "18fTqPGgeoqPyu8siswLF7bDfojnwSeke6rarO1WNLFw"
SALES_SHEET_ID = "1h1PMIYaLptFQU7EnRvEF8Met5uURgXAYHRKtHgDaIM0"

# Open the sheets
inventory_sheet = client.open_by_key(INVENTORY_SHEET_ID).sheet1
sales_sheet = client.open_by_key(SALES_SHEET_ID).sheet1

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Used for flashing messages

# Login route
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == 'test' and password == '12345':
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid login credentials! Please Enter Valid credentials")
            return redirect(url_for('login'))
    return render_template('login.html')
    
 
@app.route('/logout')
def logout():
    # Clear the entire session, logging out any user
    session.clear()
    # Redirect to login page after logout
    return redirect(url_for('login'))
# Dashboard route
@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

from datetime import datetime

@app.route('/add_delete_item', methods=['GET', 'POST'])
def add_delete_item():
    # Fetch all items from the inventory at the start
    items = inventory_sheet.get_all_records()

    if request.method == 'POST':
        action = request.form['action']
        item_name = request.form['item_name']
        quantity = int(request.form['quantity'])
        
        # Always fetch threshold
        threshold = int(request.form['threshold']) if action == 'add' else None

        if action == 'add':
            item_found = False
            for item in items:
                if item['item_name'].lower() == item_name.lower():
                    # Update quantity, threshold, and last stock updated date for existing item
                    new_quantity = item['quantity'] + quantity
                    last_updated_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    
                    inventory_sheet.update_cell(items.index(item) + 2, 2, new_quantity)  # Update Quantity (Column B)
                    inventory_sheet.update_cell(items.index(item) + 2, 4, threshold)  # Update Threshold (Column D)
                    inventory_sheet.update_cell(items.index(item) + 2, 3, last_updated_date)  # Update Last Stock Updated (Column C)
                    
                    flash("Item quantity, threshold, and last stock updated date updated successfully!", "success")
                    item_found = True
                    break

            if not item_found:
                # Add new item with threshold and current date
                last_updated_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                inventory_sheet.append_row([item_name, quantity, last_updated_date, threshold])  # Last Date
                flash("Item added successfully with threshold!", "success")

        elif action == 'delete':
            item_found = False
            for idx, item in enumerate(items, start=2):
                if item['item_name'].lower() == item_name.lower():
                    inventory_sheet.delete_row(idx)
                    item_found = True
                    flash("Item deleted successfully!", "success")
                    break

            if not item_found:
                flash("Item not found!", "error")

    # Refetch inventory after any change to ensure the displayed data is up-to-date
    items = inventory_sheet.get_all_records()

    return render_template('add_delete_item.html', items=items)


# Low stock items
@app.route('/low_stock')
def low_stock():
    items = inventory_sheet.get_all_records()
    # Check if the item quantity is below the threshold, converting to integers
    low_stock_items = [item for item in items if int(item['quantity']) < int(item['threshold'])]
    return render_template('low_stock.html', low_stock_items=low_stock_items)

# Billing

# Assuming sales_sheet and inventory_sheet are already defined and connected to your database or Google Sheets
 # Correct import statement

@app.route('/billing', methods=['GET', 'POST'])
def billing():
    if request.method == 'POST':
        try:
            # Collect form data
            receipt_no = request.form['receipt_no']
            items_bought = [item.strip() for item in request.form.getlist('item_name[]')]
            quantities = [int(q.strip()) for q in request.form.getlist('quantity[]')]
            total_amount = request.form['total_amount']
            payment_mode = request.form['payment_mode']

            # Validate total_amount
            if not total_amount or not total_amount.replace('.', '', 1).isdigit():
                flash('Total amount is invalid.')
                return redirect(url_for('billing'))

            total_amount = float(total_amount)

            # Fetch inventory data
            inventory_data = inventory_sheet.get_all_records()
            inventory_dict = {item['item_name'].strip(): item for item in inventory_data}

            items_list = []
            low_stock_items = []
            insufficient_stock = False

            # Check quantities
            for item_name, quantity in zip(items_bought, quantities):
                item_name = item_name.strip()  # Remove extra spaces
                item_data = inventory_dict.get(item_name)

                if item_data:
                    current_stock = int(item_data['quantity'])

                    if current_stock < quantity:
                        low_stock_items.append(item_name)
                        insufficient_stock = True
                    else:
                        items_list.append(f"{item_name} (x{quantity})")
                else:
                    flash(f"Item '{item_name}' not found in inventory.")
                    return redirect(url_for('billing'))

            if insufficient_stock:
                flash(f"Low stock for: {', '.join(low_stock_items)}. Please adjust quantities.")
                return redirect(url_for('billing'))

            # Record billing details
            date = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
            sales_sheet.append_row([receipt_no, ', '.join(items_list), date, total_amount, payment_mode])

            # Update inventory
            for item_name, quantity in zip(items_bought, quantities):
                item_name = item_name.strip()
                item_data = inventory_dict.get(item_name)
                if item_data:
                    current_stock = int(item_data['quantity'])
                    new_stock = current_stock - quantity

                    row = inventory_data.index(item_data) + 2
                    inventory_sheet.update_cell(row, 2, new_stock)

            flash("Billing completed successfully!")
            return redirect(url_for('billing'))

        except Exception as e:
            flash(f"An error occurred during billing: {str(e)}")
            return redirect(url_for('billing'))

    # Load inventory items
    items = inventory_sheet.get_all_records()
    return render_template('billing.html', items=items)

from datetime import datetime

@app.route('/update_stock', methods=['GET', 'POST'])
def update_stock():
    if request.method == 'POST':
        try:
            item_name = request.form['item_name'].strip()
            quantity = int(request.form['quantity'])
            action = request.form['action']
            items = inventory_sheet.get_all_records()

            item_found = False
            for index, item in enumerate(items):
                if item['item_name'].strip().lower() == item_name.lower():
                    # Determine new quantity based on action
                    if action == 'update':
                        new_quantity = item['quantity'] + quantity
                    elif action == 'remove':
                        new_quantity = item['quantity'] - quantity
                    else:
                        raise ValueError('Invalid action specified.')

                    # Ensure quantity doesn't go below zero
                    if new_quantity < 0:
                        flash("Stock cannot be negative!")
                        return redirect(url_for('update_stock'))

                    # Update the quantity in the sheet
                    inventory_sheet.update_cell(index + 2, 2, new_quantity)  # Update Quantity (Column B)

                    # Update the last updated date in Column C
                    current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    inventory_sheet.update_cell(index + 2, 3, current_date)  # Last Updated Date (Column C)

                    # Update the threshold if necessary (assuming it should remain unchanged)
                    # Optionally update threshold or perform additional logic here

                    item_found = True
                    flash("Stock updated successfully!")
                    break

            if not item_found:
                flash("Item not found!")

        except Exception as e:
            flash(f"An error occurred: {str(e)}")

        return redirect(url_for('update_stock'))

    # If GET request, display all items
    items = inventory_sheet.get_all_records()
    return render_template('update_stock.html', items=items)
    
@app.route('/check_inventory', methods=['GET'])
def check_inventory():
    # Fetch all records from the inventory Google Sheet
    items = inventory_sheet.get_all_records()

    # Return the `check_inventory.html` template along with the fetched inventory data
    return render_template('check_inventory.html', items=items)

@app.route('/report', methods=['GET', 'POST'])
def report():
    payment_methods = {}

    if request.method == 'POST':
        start_date_str = request.form.get('start_date')
        end_date_str = request.form.get('end_date')

        if 'today_sales' in request.form:
            # Get today's sales
            today = date.today()
            filtered_sales = [
                sale for sale in sales_sheet.get_all_records()
                if datetime.strptime(sale['date'], '%Y-%m-%d %H:%M:%S').date() == today
            ]
            payment_methods = group_by_payment_method(filtered_sales)
            return render_template('report.html', 
                                   filtered_sales=filtered_sales,
                                   total_transactions=len(filtered_sales),
                                   total_sales=sum(sale['total_amount'] for sale in filtered_sales if 'total_amount' in sale),
                                   payment_methods=payment_methods,
                                   start_date=None, 
                                   end_date=None)

        if not start_date_str or not end_date_str:
            flash('Start Date and End Date are required!', 'error')
            return redirect(url_for('report'))

        try:
            start_date = datetime.strptime(start_date_str, '%d-%m-%Y').date()
            end_date = datetime.strptime(end_date_str, '%d-%m-%Y').date()

            all_sales = sales_sheet.get_all_records()
            filtered_sales = [
                sale for sale in all_sales
                if start_date <= datetime.strptime(sale['date'], '%Y-%m-%d %H:%M:%S').date() <= end_date
            ]

            payment_methods = group_by_payment_method(filtered_sales)
            return render_template('report.html', 
                                   total_transactions=len(filtered_sales),
                                   total_sales=sum(sale['total_amount'] for sale in filtered_sales if 'total_amount' in sale),
                                   payment_methods=payment_methods, 
                                   start_date=start_date_str, 
                                   end_date=end_date_str)
        except Exception as e:
            flash(f'An error occurred: {str(e)}', 'error')
            return redirect(url_for('report'))

    return render_template('report.html', payment_methods=payment_methods)

from collections import defaultdict

@app.route('/download_report', methods=['POST'])
def download_report():
    start_date_str = request.form.get('start_date', '').strip()
    end_date_str = request.form.get('end_date', '').strip()

    # Check if either date is empty
    if not start_date_str or not end_date_str:
        flash('Please provide both start and end dates.', 'error')
        return redirect(url_for('report'))

    try:
        start_date = datetime.strptime(start_date_str, '%d-%m-%Y').date()
        end_date = datetime.strptime(end_date_str, '%d-%m-%Y').date()
    except ValueError:
        flash('Invalid date format. Please use DD-MM-YYYY.', 'error')
        return redirect(url_for('report'))

    all_sales = sales_sheet.get_all_records()  # Replace this with your sales data retrieval
    filtered_sales = [
        sale for sale in all_sales
        if start_date <= datetime.strptime(sale['date'], '%Y-%m-%d %H:%M:%S').date() <= end_date
    ]

    # Prepare data grouped by date and payment method
    data = defaultdict(lambda: {'Total Cash': 0, 'Total Credit': 0, 'Total Online': 0})

    for sale in filtered_sales:
        sale_date = datetime.strptime(sale['date'], '%Y-%m-%d %H:%M:%S').date()
        payment_method = sale.get('mode_of_payment', 'Unknown')

        # Update totals based on payment method
        if payment_method == 'Cash':
            data[sale_date]['Total Cash'] += sale.get('total_amount', 0)
        elif payment_method == 'Credit':
            data[sale_date]['Total Credit'] += sale.get('total_amount', 0)
        elif payment_method == 'Online':
            data[sale_date]['Total Online'] += sale.get('total_amount', 0)

    # Prepare DataFrame
    rows = []
    for sale_date, totals in data.items():
        total_sales = totals['Total Cash'] + totals['Total Credit'] + totals['Total Online']
        rows.append({
            'Date': sale_date,
            'Total Cash': totals['Total Cash'],
            'Total Credit': totals['Total Credit'],
            'Total Online': totals['Total Online'],
            'Total Sales': total_sales  # Add total sales for the day
        })

    df = pd.DataFrame(rows)

    # Create a BytesIO buffer for the Excel file
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Sales Report')
    output.seek(0)
    filename = f'sales_report_{start_date_str}_{end_date_str}.xlsx'
    return send_file(output, download_name=filename, as_attachment=True)
    

def group_by_payment_method(sales):
    payment_methods = {}
    for sale in sales:
        method = sale.get('mode_of_payment', 'Unknown')
        if method not in payment_methods:
            payment_methods[method] = {'total_amount': 0, 'transactions': 0}
        payment_methods[method]['total_amount'] += sale.get('total_amount', 0)
        payment_methods[method]['transactions'] += 1
    return payment_methods
    
if __name__ == '__main__':
    app.run(debug=True)
