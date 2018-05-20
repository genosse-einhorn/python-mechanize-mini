#!/usr/bin/env python3

from mechanize_mini import *
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
    if 'Eingegangene Nachrichten:' not in page.document_element.text_content:
        raise Exception("Login Failed, page html="+page.document_element.outer_html)

    resultlink = page.query_selector('a:contains(Prüfungsergebnisse)')
    assert isinstance(resultlink, HtmlAnchorElement)
    page = resultlink.follow()

    semesterform = page.query_selector('#semesterchange')
    assert isinstance(semesterform, HtmlFormElement)
    semesterbox = semesterform.query_selector('select')
    assert isinstance(semesterbox, HtmlSelectElement)

    for semester in semesterbox.options:
        semesterbox.value = semester.value

        semesterpage = semesterform.submit()

        # open exam windows
        for detaillink in semesterpage.query_selector_all('a:contains(Prüfungen)'):
            assert isinstance(detaillink, HtmlAnchorElement)
            exampage = detaillink.follow()

            moduleheader = exampage.query_selector('h1')
            assert moduleheader is not None
            module = moduleheader.text_content

            # take the first table
            gradetable = exampage.query_selector('table')
            assert gradetable is not None
            header1 = ''
            header2 = ''
            for graderow in gradetable.query_selector_all('tr'):
                gradecells = list(graderow.query_selector_all('.tbdata'))
                head1td = graderow.query_selector('.level01')
                head2td = graderow.query_selector('.level02')

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
