#!/usr/bin/env python3

from mechanize_mini import Browser
import sys

def main() -> None:
    user = sys.argv[1]
    pw = sys.argv[2]

    url = 'https://dualis.dhbw.de/'

    browser = Browser('DUALIS Grade Scraper / Watcher Bot (jonas@kuemmerlin.eu)')

    page = browser.open(url)

    form = page.forms['cn_loginForm']
    form.set_field('usrname', user)
    form.set_field('pass', pw);
    page = form.submit()

    # check if login succeeded
    if 'Eingegangene Nachrichten:' not in page.document.text_content:
        raise Exception("Login Failed, page html="+page.document.outer_html)

    page = page.find('.//a', text='Prüfungsergebnisse').follow()

    semesterform = page.find(id='semesterchange')
    semesterbox = semesterform.find('.//select')

    for semester in semesterbox.options:
        semesterbox.value = semester.value

        semesterpage = semesterform.submit()

        # open exam windows
        for detaillink in semesterpage.findall('.//a', text='Prüfungen'):
            exampage = detaillink.follow()

            module = exampage.find('.//h1').text_content

            # take the first table
            gradetable = exampage.find('.//table')
            header1 = ''
            header2 = ''
            for graderow in gradetable.iterfind('.//tr'):
                gradecells = graderow.findall(class_name='tbdata')
                head1td = graderow.find(class_name='level01')
                head2td = graderow.find(class_name='level02')

                if head1td is not None:
                    header1 = head1td.text_content
                if head2td is not None:
                    header2 = head2td.text_content

                if len(gradecells):
                    exam = gradecells[1].text_content
                    grade = gradecells[3].text_content

                    print("{module}\t{header1}\t{header2}\t{exam}\t{grade}\n".format(**locals()))

if __name__ == '__main__':
    main()
