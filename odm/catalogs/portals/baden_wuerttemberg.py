# -*- coding: utf-8 -*-
import re
import itertools
from lxml import html
from odm.catalogs.utils import metautils
from odm.catalogs.CatalogReader import CatalogReader

portalname = u'opendata.service-bw.de'
catalog_start_page_url = "http://opendata.service-bw.de/Seiten/offenedaten.aspx"


def categoryToODM(categorie):
    categorieToODMmap = {
        'Umwelt und Energie': 'Umwelt und Klima',
        'Bildung und Wissenschaft': 'Bildung und Wissenschaft',
        'Wirtschaft': 'Wirtschaft und Arbeit',
        'Verkehr': 'Transport und Verkehr',
        'Freizeit und Tourismus': 'Kultur, Freizeit, Sport, Tourismus',
        'Arbeit': 'Wirtschaft und Arbeit',
        u'Gebäude und Wohnen': 'Infrastruktur, Bauen und Wohnen',
        u'Bevölkerung': u'Bevölkerung',
        'Basisdaten und Geowissenschaften': 'Geographie, Geologie und Geobasisdaten',
        'Politik und Verwaltung': u'Öffentliche Verwaltung, Haushalt und Steuern'
    }
    return [categorieToODMmap[categorie]]


def licenseToODM(licenseEntry):
    if licenseEntry == u'Namensnennung':
        odmLicense = 'CC BY 3.0 DE'
    elif licenseEntry == u"Maps4BW kann im Rahmen der Umsetzung der Open-Data-Strategie des Ministeriums f\xfcr L\xe4ndlichen Raum und Verbraucherschutz Baden-W\xfcrttemberg unter den Bedingungen der Lizenz CC BY 3.0 (":
        odmLicense = u'CC BY 3.0 DE'
    elif licenseEntry == u'Namensnennung, nicht kommerziell, Weitergabe unter gleichen Bedingungen':
        odmLicense = u'CC BY-NC-SA 3.0 DE'
    elif licenseEntry == u'Keine freie Lizenz, siehe Internetseite des Datensatzes':
        odmLicense = u'other-closed'
    else:
        odmLicense = u'nicht bekannt'
    return odmLicense


def formatToODM(formatStr):
    """Returns the "allowedFormats" strings found in the argument,
    that are sourrounded by either a whitespace, a comma, a slash or brackets"""
    allowedFormats = list(metautils.fileformats) + ['PDF', 'HTML']
    fs = []
    for f in allowedFormats:
            p = re.compile("[\s,/\(]" + f + "[\s,/\)]", re.IGNORECASE)
            if p.search(' ' + formatStr + ' '):
                fs.append(f)
    return fs


def extractUrl(urlStump):
    if urlStump[:5] == "http:":
        url = urlStump
    elif urlStump[:11] == "/Documents/":
        url = u"http://" + portalname + urlStump
    else:
        url = u"http://" + portalname + u"/Seiten/" + urlStump
    return url


def nextCatalogPage(page):
    try:
        pageNavTable = page.xpath('//table[@class="ms-bottompaging"]')[0]
        forwardButton = pageNavTable.xpath('//td[@class="ms-paging"]/following-sibling::*')[0]
        onclick = forwardButton.xpath('a/@onclick')[0]
        link = re.findall('"([^"]*)"', onclick)[0]
        url = "http://" + portalname + link
        page = html.parse(url.replace(u"\\u0026", "&"))
    except:
        page = None
    return page


def getCatalogPages():
    page = html.parse(catalog_start_page_url)
    pages = []
    while page is not None:
        pages.append(page)
        page = nextCatalogPage(page)
    return pages


def scapeTableCell(table, cellName):
    try:
        row = table.xpath('.//tr[td//text()[contains(., "' + cellName + '")]]')[0]
        cell = row.xpath('td')
        val = cell[1].text
    except:
        val = ""
    return val


def scrapeCatalogPageItem(entry):
    d = {}
    d['url'] = "http://" + portalname + "/Seiten/" + entry.xpath('.//a/@href')[0]
    d['category'] = entry.xpath('.//tr' +
                                '[td//text()[contains(., "Kategorie:")]][1]' +
                                '/td[2]/a')[0].text
    return d


def scrapeCatalogPageList(catalogPage):
    entryListItems = catalogPage.xpath('//div[@class="OdpVList"]//div[@class="OdpVListElem"]')
    entryPages = map(scrapeCatalogPageItem, entryListItems)
    return entryPages


def scrapeLicense(page):
    cell = page.xpath('.//table[2]/tr[2]/td[2]/node()')[0]
    try:
        cell = cell.xpath('./text()')[0]
    except:
        None
    return cell


def scrapeCatalogEntryPage(d):
    page = html.parse(d['url'])
    p = page.xpath('//div[@class="OdpVListElem details"]')[0]

    d['title']               = p.xpath('./div/h1/text()')[0]
    d['description']         = p.xpath('.//div[2]/p/text()')[0]
    d['format']              = scapeTableCell(p.xpath('.//div[4]/table')[0], 'Format')
    d['file-url']                 = page.xpath('.//div[4]/table//a/@href')[0]
    d['nutzungsbedingungen'] = scrapeLicense(p)
    d['herausgeber']         = scapeTableCell(p.xpath('.//div[6]//table')[0], 'Herausgeber des Datensatzes:')
    d['beschreibende stelle']= scapeTableCell(p.xpath('.//div[6]//table')[0], 'Datensatz beschreibende Stelle:')  # unused

    d['stichtag'] = scapeTableCell(p.xpath('./table')[0], 'Stichtag:')
    d['zeitraum'] = scapeTableCell(p.xpath('./table')[0], 'Zeitraum:')
    d['publiziert am'] = scapeTableCell(p.xpath('.//div[6]//table')[0], 'Zuletzt publiziert oder aktualisiert')
    return d


def toDB(rec):
    db = {}
    db['city'] = 'badenwuerttemberg'  # Baden-Württenberg is not a city ?!
    db['source'] = 'd'
    db['costs'] = None

    db['categories'] = categoryToODM(rec['category'])
    db['url'] = rec['url']
    db['title'] = rec['title']
    db['description'] = rec['description']
    db['publisher'] = rec['herausgeber']
    db['filelist'] = [extractUrl(rec['file-url'])]
    db['formats'] = formatToODM(rec['format'])
    db['licenseshort'] = licenseToODM(rec['nutzungsbedingungen'])
    temps = filter(lambda x: x != "",
                   [rec['zeitraum'], rec['stichtag'], rec['publiziert am']])
    db['temporalextent'] = temps[0] if temps else None
    db['open'] = metautils.isopen(db['licenseshort'])
    db['spatial'] = False

    db['metadata'] = ''
    db['metadata_xml'] = None

    return db


class BwReader(CatalogReader):
    def info(self):
        return {
            'name': 'bw_harvester',
            'title': u'opendata.service-bw.de',
            'description': u'Harvester for Baden-Württembergs open data portal opendata.service-bw.de'
        }

    def gather(self):
        catalogPages = getCatalogPages()
        catalogItemDicts = map(scrapeCatalogPageList, catalogPages)
        catalogItemDicts = list(itertools.chain(*catalogItemDicts))
        return catalogItemDicts

    def fetch(self, d):
        d = scrapeCatalogEntryPage(d)
        return d

    def import_data(self, rec):
        db = toDB(rec)
        db['originating_portal'] = portalname
        db['accepted'] = True
        return db
