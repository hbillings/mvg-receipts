#!usr/bin/python

import StringIO
import csv
import os
import re
from datetime import datetime
from flask import Flask, request, render_template, make_response

app = Flask(__name__)

# Views
@app.route('/', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        file = request.files['receipts']
        # file.save("input.txt")
        return download(file)

    return render_template('upload.html')


@app.route('/download')
def download(file):

    class Receipt(object):
        def __init__(self, **kwargs):
            self.deposit_id = None  # formatted date of latest entry. Populate after all instances are instantiated.
            self.phone = self.formatPhone(kwargs["phone"])
            self.customer = self.concatNames(kwargs["first_name"], kwargs["last_name"])
            self.transaction_id = kwargs["transaction_id"]
            self.date = kwargs["date"]  # modified later to be date of latest entry
            self.cash_account_id = '11000'  # get da monies
            self.total = self.checkForCredits(kwargs["total"], kwargs["action_code"])
            self.prepayment = 'TRUE'  # for Peachtree
            self.num_of_distros = '1'  # for Peachtree
            self.invoice_paid = ''  # left empty; unsure if necessary
            self.gl_account_id = '12000'
            self.gl_amount = self.total * -1  # is this still x-1 when total is negative?

        def checkForCredits(self, total, action_code):
            """
            Change Total Amount to number, and, if row has an Action Code of CREDIT, change sign.
            """
            return float(total) * -1 if action_code == "CREDIT" else float(total)

        def formatPhone(self, phone):
            """
            Strip formatting of phone number.
            """
            return re.sub(r'[^a-zA-Z0-9]', '', phone)

        def concatNames(self, first, last):
            """
            Join names into one field.
            """
            return " ".join([first, last])

        def toDict(self):
            return {
                "deposit_id": self.deposit_id,
                "phone": self.phone,
                "customer": self.customer,
                "transaction_id": self.transaction_id,
                "date": self.date,
                "cash_account_id": self.cash_account_id,
                "total": self.total,
                "prepayment": self.prepayment,
                "num_of_distros": self.num_of_distros,
                "invoice_paid": self.invoice_paid,
                "gl_account_id": self.gl_account_id,
                "gl_amount": self.gl_amount
            }


    def readReceipts(file):
        """
        Open tab-delimited file, pluck out headers we care about,
        and save as a list of objects.
        """
        data = []
        tsvreader = csv.DictReader(file, delimiter='\t', quotechar='|')
        for row in tsvreader:
            for col in row:
                col.decode('utf-8')
            if row["Response Code"] != "2" and row["Action Code"] != "VOID":
                new_receipt = Receipt(**{
                    "phone": row["Phone"],
                    "first_name": row["Customer First Name"],
                    "last_name": row["Customer Last Name"],
                    "transaction_id": row["Transaction ID"],
                    "date": row["Submit Date/Time"],
                    "total": row["Total Amount"],
                    "action_code": row["Action Code"] # not written to output file
                })
                data.append(new_receipt)

        return convertToCsv(standardizeDate(data))


    def convertToCsv(data):
        output = StringIO.StringIO()
        rows = [row.toDict() for row in data]
        writer = csv.DictWriter(output, rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
        return output.getvalue()


    def standardizeDate(data):
        latest_date = data[-1].date
        parsed_date = datetime.strptime(latest_date, "%d-%b-%Y %I:%M:%S %p %Z")

        """
        Create Date column equal to last entry's day, in format 04/17/16.
        """
        batch_date = '%s/%s/%s' % (str(format(parsed_date.month, '02')), str(parsed_date.day), str(parsed_date.year)[2:])

        """
        Create six-digit Deposit ID from the last instance's Date, in format 041716.
        """
        deposit_id = '%s%s%s' % (str(format(parsed_date.month, '02')), str(parsed_date.day), str(parsed_date.year)[2:])

        for receipt in data:
            receipt.date = batch_date
            receipt.deposit_id = deposit_id

        return data

    output = readReceipts(file)
    response = make_response(output)
    response.headers["Content-Disposition"] = "attachment; filename=receipts.csv"
    return response
    # return render_template('/download.html', output=output)


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
