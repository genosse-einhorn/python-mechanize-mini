#!/usr/bin/env python3

import mechanize_mini as minimech
import mechanize_mini.HtmlTree as HT
import xml.etree.ElementTree as ET
import sys

user = sys.argv[1]
pw = sys.argv[2]

url = 'https://dualis.dhbw.de/'

browser = minimech.Browser('DUALIS Grade Scraper / Watcher Bot (jonas@kuemmerlin.eu)')

page = browser.open(url)

form = page.find_form(name='cn_loginForm');
form.set_field('usrname', user)
form.set_field('pass', pw);
page = form.submit()

# check if login succeeded
if 'Eingegangene Nachrichten:' not in HT.text_content(page.document.getroot()):
    raise Exception("Login Failed")

page = page.follow_link(text='Prüfungsergebnisse');

semesterform = page.find_form(id='semesterchange')
semesterbox = semesterform.find_input(type='select')

for semester in semesterbox.available_option_values:
    semesterbox.value = semester

    semesterpage = semesterform.submit()

    # open exam windows
    for detaillink in semesterpage.find_all_links(text='Prüfungen'):
        exampage = semesterpage.open(detaillink.get('href'))

        module = HT.text_content(exampage.find_element(tag='h1'))

        # take the first table
        gradetable = exampage.find_element(tag='table', n=0)
        header1 = ''
        header2 = ''
        for graderow in HT.find_all_elements(gradetable, tag='tr'):
            gradecells = list(HT.find_all_elements(graderow, class_name='tbdata'))
            head1td = next(HT.find_all_elements(graderow, class_name='level01'), None)
            head2td = next(HT.find_all_elements(graderow, class_name='level02'), None)

            if head1td:
                header1 = HT.text_content(head1td)
            if head2td:
                header2 = HT.text_content(head2td)

            if len(gradecells):
                exam = HT.text_content(gradecells[1])
                grade = HT.text_content(gradecells[3])

                print("{module}\t{header1}\t{header2}\t{exam}\t{grade}\n".format(**locals()))
