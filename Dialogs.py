# Dialogs.py

from PyQt5.QtWidgets import QInputDialog, QLineEdit, QMessageBox
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import QTimer, Qt

def Set_Password_Dialog(self):
    # 2. Create and Customize the Dialog
    Password_dialog = QInputDialog(self)
    Password_dialog.setWindowTitle("Security Check")
    Password_dialog.setLabelText("Enter Administrator Password:")
    Password_dialog.setWindowIcon(QIcon("logo2424.png"))
    Password_dialog.setTextEchoMode(QLineEdit.Password)

    # Enable the ? button in the title bar
    Password_dialog.setWindowFlags(Password_dialog.windowFlags() | Qt.WindowContextHelpButtonHint)
    # Set the What's This text explaining the purpose
    Password_dialog.setWhatsThis("This dialog requires the administrator password to grant access to the Maintenance Console, where you can view logs and perform remote commands.")

    # --- STYLING: Increase Size and Font ---
    # We use CSS to force the dialog to be bigger and have large text
    Password_dialog.setStyleSheet("""

        QDialog {
            min-width: 400px;  /* Make the window wider */
            min-height: 200px; /* Make the window taller */
        }
        QLabel {
            font-size: 18px;   /* Larger label text */
            font-weight: bold;
        }
        QLineEdit {
            font-size: 18px;   /* Larger input text */
            padding: 5px;
        }
        QPushButton {
            font-size: 16px;   /* Larger buttons */
            padding: 8px 20px;
            min-width: 80px;
        }
        QPushButton {
        background-color: qlineargradient(
            x1:0, y1:0, x2:0, y2:1,
            stop:0 #2a4da3,
            stop:1 #1f3c88
        );

        color: white;
        font-family: "Segoe UI";
        font-size: 13px;
        font-weight: 600;

        padding: 8px 20px;
        padding-bottom: 10px;

        border-radius: 8px;
        border: 1px solid #142a5c;
        }

        QPushButton:hover {
        background-color: qlineargradient(
            x1:0, y1:0, x2:0, y2:1,
            stop:0 #4fc3dc,
            stop:1 #1f3c88
        );
    }

    QPushButton:pressed {
        background-color: #1f3c88;
        padding-top: 10px;
        padding-bottom: 8px;
    }

    QPushButton:disabled {
        background-color: #9fb0d9;
        color: #eeeeee;
        border: 1px solid #7a8bb5;
    }

    """)
    # ---------------------------------------

    # 3. Execute the dialog
    ok = Password_dialog.exec_()
    password = Password_dialog.textValue()
    return password, ok

def Show_Access_Denied(self):
    # Create and Customize the MessageBox
    msg = QMessageBox(self)
    msg.setWindowTitle("Access Denied")
    msg.setText("Incorrect password.")
    msg.setIcon(QMessageBox.Warning)
    msg.setWindowIcon(QIcon("logo2424.png"))

    # Styling: Red theme for error
    msg.setStyleSheet("""
        QMessageBox {
            min-width: 400px;
            min-height: 200px;
            background-color: #ffffff;
        }
        QLabel {
            font-size: 18px;
            font-weight: bold;
            color: #d32f2f;  /* Red text */
        }
        QPushButton {
            font-size: 16px;
            padding: 8px 20px;
            min-width: 80px;
            background-color: qlineargradient(
                x1:0, y1:0, x2:0, y2:1,
                stop:0 #d32f2f,  /* Red gradient */
                stop:1 #b71c1c
            );
            color: white;
            border-radius: 8px;
            border: 1px solid #b71c1c;
        }
        QPushButton:hover {
            background-color: qlineargradient(
                x1:0, y1:0, x2:0, y2:1,
                stop:0 #ef5350,
                stop:1 #d32f2f
            );
        }
        QPushButton:pressed {
            background-color: #b71c1c;
        }
        QPushButton:disabled {
            background-color: #e57373;
            color: #eeeeee;
            border: 1px solid #e57373;
        }
    """)
    msg.exec_()

def Show_Access_Granted(self):
    # Create and Customize the MessageBox for success
    msg = QMessageBox(self)
    msg.setWindowTitle("Access Granted")
    msg.setText("Welcome to Maintenance Console!")
    msg.setIcon(QMessageBox.Information)
    msg.setWindowIcon(QIcon("logo2424.png"))
    msg.setStandardButtons(QMessageBox.NoButton)  # No buttons for auto-close

    # Styling: Green theme for success
    msg.setStyleSheet("""
        QMessageBox {
            min-width: 400px;
            min-height: 200px;
            background-color: #ffffff;
        }
        QLabel {
            font-size: 18px;
            font-weight: bold;
            color: #388e3c;  /* Green text */
        }
    """)
    msg.show()
    # Auto-close after 2 seconds using done(0) for proper closure
    QTimer.singleShot(2000, lambda: msg.done(0))