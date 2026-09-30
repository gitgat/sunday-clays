"""Fake `pdftotext -layout` output in the real layout, with invented names and a three-station course."""

TYPED = """                                   Sunday Clays Update
                                        Sunday, May 31, 2026
                                        COMMENTARY by Someone
RESULTS: Somebody did it again.

       Published weekly by Someone, edited by Someone Else                       Page 1 of 3
                    Sunday Clays Update
                              Sunday, May 31, 2026


                               Sunday, May 31, 2026
               Note Place   Name                     Hits    Class
                      1     Testerson, Ann             22               1
                      2     Fakeman, Bo                21               2
                            Mockley, Cy                20   28 Gauge    3
                PB          Benedetto, Di                 20               4
                G           Dummy, Ed                  18               5
                N           O'Sample, Flo              15   20 Gauge    6
               NG           Van Der Test, Gus          10               7
                                                   126
                                   Average Score     18.0    72.0%
                G     =     Guest
                                                   Zed, Not Aresult    99
Published weekly by Someone, edited by Someone Else                       Page 2 of 3
                    Sunday Clays Update
                             Sunday, May 31, 2026
                                        COURSE 372-7-SSP.xlsx                   5/31/26

                             COURSE ARRANGEMENT SHEET
                                            Event Date
                                       Sunday, May 31, 2026
                                                                       Target
                       Stn. Tgts Rep. Presentation             Traps   Count
                        2    7    1 SINGLE                       A       1
                                  1 SINGLE                       B       1
                                  1 REPORT PAIR                 D-A      2
                                  1 REPORT PAIR                 A-B      2
                                  1 TRUE PAIR                   B-A      1

                       Stn. Tgts
                        4    7     1   SINGLE                    A       1
                                   3   REPORT PAIR              B-C      6

                       Stn. Tgts
                        7    8     1   SINGLE                    B       1
                                   1   REPORT PAIR              B-D      2
                                   1   TRUE PAIR                C-D      2
                                   1   TRUE PAIR                C-D      3

                       Stn. Tgts
                        2    7     1   SINGLE                    A       1

                                                     Targets      22    22
Published weekly by Someone, edited by Someone Else                       Page 3 of 3
"""

# pdftotext puts a form feed after each page; the scan page has no text.
PDF_TEXT = TYPED + "\f" + "\n\f"


_RESULTS_PAGE = TYPED.split("Published weekly by Someone, edited by Someone Else                       Page 2 of 3")[0]
_COMMENTARY = "Someone wrote a long chatty commentary about the weather and the birds today. " * 4

# Results typed but the course sheet is a picture: page 1 results, page 2 (footer only) course picture, page 3 scans.
PDF_TEXT_IMAGE_COURSE = _RESULTS_PAGE + "\f" + "Published weekly by Someone       Page 2 of 3\n\f" + "\n\f"

# Results and course are both pictures: page 1 commentary, page 2 results picture, page 3 course picture, page 4 scans.
_FOOTER = "Published weekly by Someone       Page 2 of 4\n"
PDF_TEXT_IMAGE_BOTH = _COMMENTARY + "\f" + _FOOTER + "\f" + _FOOTER + "\f" + "\n\f"

# Results typed, picture course, and no page after the results: nothing to read the course from.
PDF_TEXT_NO_COURSE_PAGE = _RESULTS_PAGE + "\f"

# Typed results, no typed course, no picture pages at all: the first page after the results is a blank scoresheet.
PDF_TEXT_RESULTS_THEN_SCANS = _RESULTS_PAGE + "\f" + "\n\f" + "\n\f"
