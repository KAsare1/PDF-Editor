import fitz  # PyMuPDF
import logging
from PyQt6.QtWidgets import (QWidget, QHBoxLayout, QScrollArea, QVBoxLayout, QLabel, QSplitter, QTableWidget,
                             QTableWidgetItem, QHeaderView, QSlider, QLineEdit, QMessageBox, QInputDialog)
from PyQt6.QtCore import Qt, QMimeData, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap, QDrag



class PDFPageLabel(QLabel):
    pdf_click = pyqtSignal(object)  # Custom signal to handle click events

    def __init__(self, page, scale_factor, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.page = page
        self.scale_factor = scale_factor

    def mousePressEvent(self, event):
        # Emit a custom signal when the user clicks on the label
        if event.button() == Qt.MouseButton.LeftButton:
            self.pdf_click.emit(event)

def create_pdf_viewer_widget(pdf_path, pdf_document):
    try:
        widget = QWidget()
        layout = QHBoxLayout()
        widget.setLayout(layout)
        widget.pdf_path = pdf_path  # Store the pdf_path in the widget
        widget.pdf_document = pdf_document  # Store the PDF document in the widget
        widget.annotation_mode = None  # Default to no annotation mode
        widget.annotation_color = None
        widget.scale_factor = 1  # To manage the zoom scale
        widget.current_page = 0  # To track the currently loaded page

        # Splitter to divide the PDF view and the controls
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Scroll area for PDF content
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_area.setWidget(scroll_content)

        pdf_pages = [pdf_document.load_page(i) for i in range(len(pdf_document))]

        pdf_labels = []
        for page_index, page in enumerate(pdf_pages):
            pix = page.get_pixmap(matrix=fitz.Matrix(0.5, 0.5))  # Scale down the content
            qimage = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888)
            pixmap = QPixmap.fromImage(qimage)

            # Use the custom PDFPageLabel to handle clicks
            label = PDFPageLabel(page, widget.scale_factor)
            label.setPixmap(pixmap)
            pdf_labels.append(label)
            scroll_layout.addWidget(label)

            # Connect the custom click event to the handler
            label.pdf_click.connect(lambda event, page=page_index: widget.on_pdf_click(event, page))

            hbox = QHBoxLayout()
            hbox.addStretch(1)
            hbox.addWidget(label)
            hbox.addStretch(1)
            scroll_layout.addLayout(hbox)

        if len(pdf_pages) == 0:
            error_label = QLabel("No pages found in PDF.")
            scroll_layout.addWidget(error_label)

        splitter.addWidget(scroll_area)

        # Right side layout for metadata, zoom slider, and page navigation input
        right_layout = QVBoxLayout()

        # Metadata table
        metadata_table = QTableWidget(10, 1)
        metadata_table.setHorizontalHeaderLabels(["Value"])
        metadata_table.setVerticalHeaderLabels(["producer", "format", "encryption", "author", "modDate",
                                                "keywords", "title", "creationDate", "creator", "subject"])
        metadata = pdf_document.metadata
        fields = ["producer", "format", "encryption", "author", "modDate", "keywords", "title", "creationDate",
                  "creator", "subject"]
        for i, field in enumerate(fields):
            metadata_table.setItem(i, 0, QTableWidgetItem(metadata.get(field, '')))

        metadata_table.horizontalHeader().setStretchLastSection(True)
        metadata_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        metadata_table.setFixedHeight(300)  # Set a fixed height for the metadata table

        right_layout.addWidget(metadata_table)

        # Spacer to increase space between metadata table and other controls
        right_layout.addSpacing(20)

        # Zoom slider
        zoom_slider = QSlider(Qt.Orientation.Horizontal)
        zoom_slider.setMinimum(1)
        zoom_slider.setMaximum(5)
        zoom_slider.setValue(1)
        zoom_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        zoom_slider.setTickInterval(1)
        zoom_slider.setFixedWidth(200)  # Set a fixed width for the zoom slider
        zoom_slider.setToolTip("Zoom in and out of the PDF")  # Add tooltip
        right_layout.addWidget(zoom_slider)

        right_widget = QWidget()
        right_widget.setLayout(right_layout)
        splitter.addWidget(right_widget)

        # Set the initial sizes of the splitter to achieve the 70%/30% ratio
        splitter.setSizes([800, 400])

        layout.addWidget(splitter)


                # Annotation mode setter
        def set_annotation_mode(mode, color=None):
            widget.annotation_mode = mode
            if color:
                widget.annotation_color = color

        widget.set_annotation_mode = set_annotation_mode

        def hex_to_rgb(hex_color):
            # Remove the hash symbol if present
            hex_color = hex_color.lstrip('#')
            
            # Convert the hex code to RGB values
            return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        
        def update_pdf_pixmap(page, page_index):
            # Update the QPixmap of the PDFPageLabel
            pix = page.get_pixmap(matrix=fitz.Matrix(widget.scale_factor, widget.scale_factor))
            qimage = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888)
            pixmap = QPixmap.fromImage(qimage)
            pdf_labels[page_index].setPixmap(pixmap)

        def display_annotations(page):
            annotations = []
            for a in page.annots:
                if a.type == fitz.ANNOT_TEXT:
                    annotations.append(a.text)

            # Here you can display annotations in a message box or in a dedicated UI element
            if annotations:
                QMessageBox.information(widget, "Annotations", "\n".join(annotations), QMessageBox.Ok)

        def on_pdf_click(event, page_index):
            if widget.annotation_mode:
                try:
                    # Load the clicked page using the page index
                    page = widget.pdf_document.load_page(page_index)
                    
                    # Get the click position, scale it accordingly
                    point = event.position()
                    x_scaled = point.x() / widget.scale_factor
                    y_scaled = point.y() / widget.scale_factor
                    fitz_point = fitz.Point(x_scaled, y_scaled)

                    # Handle different annotation modes
                    if widget.annotation_mode == "highlight":
                        # Define a rectangle around the clicked area for highlight
                        rect = fitz.Rect(x_scaled - 20, y_scaled - 5, x_scaled + 20, y_scaled + 5)
                        highlight = page.add_highlight_annot(rect)
                        
                        # Convert annotation color to RGB (if it's in hex format)
                        color = widget.annotation_color
                        if isinstance(color, str):
                            color = hex_to_rgb(color)
                        
                        # Normalize the RGB color to the range 0-1
                        normalized_color = [c / 255.0 for c in color]
                        
                        # Set the color for the highlight
                        highlight.set_colors(stroke=normalized_color)
                        highlight.update()

                        # Update the QPixmap of the PDFPageLabel
                        pix = page.get_pixmap(matrix=fitz.Matrix(widget.scale_factor, widget.scale_factor))
                        qimage = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888)
                        pixmap = QPixmap.fromImage(qimage)
                        pdf_labels[page_index].setPixmap(pixmap)

                    elif widget.annotation_mode == "comment":
                        comment_text, ok = QInputDialog.getText(widget, "Add Comment", "Enter comment:")
                        if ok and comment_text:
                            annot = page.add_text_annot(fitz_point, comment_text)
                            annot.update()
                            # Update the QPixmap of the PDFPageLabel
                            update_pdf_pixmap(page, page_index)

                            # Display all comments
                            display_annotations(page)

                    elif widget.annotation_mode == "text_note":
                        note_text, ok = QInputDialog.getText(widget, "Add Text Note", "Enter note:")
                        if ok and note_text:
                            annot = page.add_text_annot(fitz_point, note_text)
                            annot.update()
                            # Update the QPixmap of the PDFPageLabel
                            update_pdf_pixmap(page, page_index)

                            # Display all text notes
                            display_annotations(page)

                except Exception as e:
                    logging.error(f"Failed to annotate PDF: {e}")
                    QMessageBox.critical(widget, "Error", f"Failed to annotate PDF: {e}")

                            # Update the widget or repaint the PDF to reflect the changes
                        
                widget.update()  # Assuming this repaints the PDF view with annotations

        # Assign the function to the widget's on_pdf_click event
        widget.on_pdf_click = on_pdf_click



        def save_annotations():
            try:
                widget.pdf_document.save(widget.pdf_path, incremental=True, encryption=fitz.PDF_ENCRYPT_KEEP)
                QMessageBox.information(widget, "Success", "Annotations saved successfully.")
            except Exception as e:
                logging.error(f"Failed to save annotations: {e}")
                QMessageBox.critical(widget, "Error", f"Failed to save annotations: {e}")

        widget.save_annotations = save_annotations
        

        def zoom_pdf():
            try:
                scale_factor = zoom_slider.value()
                for i, page in enumerate(pdf_pages):
                    pix = page.get_pixmap(matrix=fitz.Matrix(scale_factor, scale_factor))
                    qimage = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888)
                    pixmap = QPixmap.fromImage(qimage)
                    pdf_labels[i].setPixmap(pixmap)
            except Exception as e:
                logging.error(f"Failed to zoom PDF: {e}")
                QMessageBox.critical(widget, 'Error', f'Failed to zoom PDF: {e}')

        zoom_slider.valueChanged.connect(zoom_pdf)

        return widget
    except Exception as e:
        logging.error(f"Failed to create PDF viewer widget: {e}")
        QMessageBox.critical(widget, 'Error', f'Failed to create PDF viewer widget: {e}')

class DraggableLabel(QLabel):
    def __init__(self, parent=None, dialog=None):
        super().__init__(parent)
        self.dialog = dialog
        self.setAcceptDrops(True)

    def mousePressEvent(self, event):
        try:
            if event.button() == Qt.MouseButton.LeftButton:
                drag = QDrag(self)
                mime_data = QMimeData()
                mime_data.setText(str(self.objectName()))
                drag.setMimeData(mime_data)
                drag.exec(Qt.DropAction.MoveAction)
        except Exception as e:
            logging.error(f"Failed in mousePressEvent: {e}")
            QMessageBox.critical(self, 'Error', f'Failed in mousePressEvent: {e}')

    def dragEnterEvent(self, event):
        try:
            if event.mimeData().hasText():
                event.acceptProposedAction()
        except Exception as e:
            logging.error(f"Failed in dragEnterEvent: {e}")
            QMessageBox.critical(self, 'Error', f'Failed in dragEnterEvent: {e}')

    def dragMoveEvent(self, event):
        try:
            if event.mimeData().hasText():
                event.acceptProposedAction()
        except Exception as e:
            logging.error(f"Failed in dragMoveEvent: {e}")
            QMessageBox.critical(self, 'Error', f'Failed in dragMoveEvent: {e}')

    def dropEvent(self, event):
        try:
            if event.mimeData().hasText():
                source_widget = event.source()
                if source_widget:
                    source_index = int(source_widget.objectName())
                    target_index = int(self.objectName())
                    event.setDropAction(Qt.DropAction.MoveAction)
                    event.accept()
                    self.dialog.swapWidgets(source_index, target_index)
        except Exception as e:
            logging.error(f"Failed in dropEvent: {e}")
            QMessageBox.critical(self, 'Error', f'Failed in dropEvent: {e}')
