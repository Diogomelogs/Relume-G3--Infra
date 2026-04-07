def anchor_dates_to_layout(dates, layout_spans):

    anchored = []

    for d in dates:

        for span in layout_spans:

            if d["raw"] in span["text"]:

                anchored.append({
                    "date_iso": d["iso"],
                    "page": span["page"],
                    "bbox": span["bbox"],
                    "text": span["text"]
                })

    return anchored