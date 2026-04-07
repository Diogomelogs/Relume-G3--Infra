from reportlab.pdfgen import canvas

def export_dossier(case):

    c = canvas.Canvas("dossier.pdf")

    y = 800

    for event in case["timeline"]:

        line = f'{event["date"]} - {event["label"]}'

        c.drawString(50, y, line)

        y -= 20

    c.save()