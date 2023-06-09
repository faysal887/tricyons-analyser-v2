import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

import pandas as pd
import time, requests, csv, json
from datetime import datetime

import sys, os, shutil, pdb
sys.path.insert(1, '/Users/muhammadfaisal/Documents/')

from pathlib import Path
import urllib.request
from bs4 import BeautifulSoup

from tabula.io import read_pdf


def make_first_row_header(df):
    new_header = df.iloc[0] #grab the first row for the header
    df = df[1:] #take the data less the header row
    df.columns = new_header

    return df


def get_catalog_google_sheets(catalog_link):
    try:
        # domain = urlparse(catalog_link).netloc
        segments = catalog_link.rpartition('/')
        link = f"{segments[0]}/export?format=csv"
        file = requests.get(link)
        if file.status_code == 200:
            fileContent = file.content.decode('utf-8')

            reader = csv.reader(fileContent.split('\n'), delimiter=',')
            df=pd.DataFrame(reader)

            df=make_first_row_header(df)
            # df.to_excel(f'{catalog_dir}/catalog.xlsx')
            return df
        else:
            return pd.DataFrame()
    except Exception as e:
        print(e)
        return pd.DataFrame()


def get_catalog_google_sheets_2(url, sheet_name, headers=None):
    # palletfly, coralport all sheets
    try:
        if headers: content = requests.get(url, headers=headers).content
        else: content = requests.get(url).content
        
        xl = pd.ExcelFile(content)
        df=pd.DataFrame(xl.book[sheet_name].values) 
        return df
    except Exception as e:
        print(e)
        return pd.DataFrame()


def get_catalog_google_sheets_3(url):
    # nexdeal
    try:
        df=pd.read_csv(url)
        return df
    except Exception as e:
        return pd.DataFrame()


def get_catalog_google_sheets_4(url):
    try:
        file = requests.get(url)
        if file.status_code == 200:
            fileContent = file.content.decode('utf-8')

            reader = csv.reader(fileContent.split('\n'), delimiter=',')
            df=pd.DataFrame(reader)

            df=make_first_row_header(df)
            return df
        else:
            return pd.DataFrame()
    except Exception as e:
        print(e)
        return pd.DataFrame()


def convert_to_xlsx(read_path):
    with open(read_path) as xml_file:
        soup = BeautifulSoup(xml_file.read(), 'xml')
        # writer = pd.ExcelWriter(save_path_xlsx)
        for sheet in soup.findAll('Worksheet'):
            sheet_as_list = []
            for row in sheet.findAll('Row'):
                sheet_as_list.append([cell.Data.text if cell.Data else '' for cell in row.findAll('Cell')])
            df=pd.DataFrame(sheet_as_list)
            df=make_first_row_header(df)
            # df.to_excel(writer, sheet_name=sheet.attrs['ss:Name'], index=False, header=False)
        # writer.save() 

    return df


def download_file_urllib(url, save_path):
    urllib.request.urlretrieve(url, save_path)
    
            
def strip_column_names(df):
    df=df.rename(columns=lambda x: x.strip() if x!=None else 'Unnamed')
    return df


def preprocess_price(df):
    # df.each_price = df.each_price.apply(lambda x: str(x).strip().split()[0] if len(str(x).split())>1 else x) # some catalogs had a price written as '$ 49.50 60', so we are only take this first float value
    
    # Regular expression pattern to extract a float/integer with an optional $ sign, float can contain , or .
    price_pattern = r"\$?\s*\d[,.\d]?"
    df=df[df.each_price.astype(str).str.contains(price_pattern, regex=True, na=False)]
    df.each_price=df.each_price.astype(str).str.replace(' ','', regex=False)
    df.each_price = df.each_price.astype(str).str.replace('$', '', regex=False).str.replace('\n', '', regex=False).str.replace(',', '', regex=False).astype(float)
    return df


def preprocess_upc(df):
    df.upc = df.upc.fillna(000000)
    df.upc = df.upc.astype(str).str.replace(' ', '',regex=False).str.replace('.0', '',regex=False).str.replace('-', '',regex=False).str.replace('+', '',regex=False).str.replace('.', '',regex=False)
    df['upc'] = pd.to_numeric(df['upc'], errors='coerce')
    df = df.dropna(subset=['upc'])
    df.upc = df.upc.astype(int).astype(str).str.zfill(12)

    return df


def label_data(df, catalogs):
    df=df.reset_index(drop=True)
    df = df.loc[:, ~df.columns.str.contains('Unnamed', case=False, regex=False)]

    # when looping first time or columns already exists
    try:    df[['id_columns_name', 'id_columns_type', 'price_column']].fillna('not_found', inplace=True)
    except: df[['id_columns_name', 'id_columns_type', 'price_column']]=None

    # only loop on missing labels rows
    unlabeled_suppliers=df[df.id_columns_name.isnull()].Distributor.tolist()
    if unlabeled_suppliers: print('These suppliers are unlabelled: ', unlabeled_suppliers)
        # interact(display_df, supplier_name=unlabeled_suppliers)
    else: 
        print(f"All Suppliers are Labeled")
        for name, tmpdf in catalogs.items():
            try:    
                # tmpdf=catalogs[row.Distributor]

                # record/row in LINKS sheet
                record = df[df.Distributor==name]
                
                # asin or upc
                if record.id_columns_type.item()=='asin':
                    tmpdf['asin'] = tmpdf[record.id_columns_name.item()].copy()
                elif record.id_columns_type.item()=='upc':
                    tmpdf['upc'] = tmpdf[record.id_columns_name.item()].copy()

                tmpdf['each_price'] = tmpdf[record.price_column.item()].copy()
                tmpdf['distributor'] = record.Distributor.item()


                catalogs[record.Distributor.item()] = tmpdf
            except Exception as e:
                exc_type, exc_obj, exc_tb = sys.exc_info()
                fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                print(e, exc_type, fname, exc_tb.tb_lineno)

    return df, catalogs

        

def preprocess_nuk(df):
    df=df[df.upc!='assorted']
    return df

  
def preprocess_bgsales(df):
    df['upc'] = df['upc'].str.replace('UPC CODE: ', '')
    df['case_pack'] = df['case_pack'].str.replace('CASE PACK: ', '')
    return df


def preprocess_ewd(tmpdf):
    tmpdf['each_price'] = tmpdf['each_price'].astype(str).str.replace('title_dp','')
    tmpdf['each_price'] = tmpdf['each_price'].astype(str).str.replace('itle_dp','')

    return tmpdf


def download_and_convert_pdf_to_excel(driveid):
    drivepath =     f'https://drive.google.com/uc?id={driveid}'

    dfs2 = read_pdf(drivepath, pages='all')

    final=pd.DataFrame()
    for i, pagedf in enumerate(dfs2):
        if i>0:
            pagedf = pagedf.columns.to_frame().T.append(pagedf, ignore_index=True)
            pagedf.columns=final.columns
            
        final=pd.concat([final, pagedf])
        print(final.shape)

    final=final.dropna(how='all').reset_index(drop=True)

    return final


def download_online_excel_catalogs(df, tmp_dir, test_catalogs=None):
    catalogs={}
    error_catalogs={}

    for i, row in df.iterrows():
        print(f'{i+1}/{len(df)}', end='\r')

        try:
            url=row['Link']
            supplier_name=row['Distributor'].lower()
            supplier_name_org=row['Distributor']
            id_column=row['id_columns_name']
            sheet_name=row['Sheet Name']

            # for testing on some specific catalogs
            test_catalogs=[x.lower() for x in test_catalogs]
            
            if test_catalogs and supplier_name not in test_catalogs: 
                continue

            if 'ecomwholesaledeals' in supplier_name:
                catalogdf = download_and_convert_pdf_to_excel(url)

            elif 'kntradingllc' in supplier_name:
                catalogdf=get_catalog_google_sheets_2(url, sheet_name='Sheet1')
                catalogdf=make_first_row_header(catalogdf)
                catalogdf=catalogdf[[x for x in catalogdf.columns.tolist() if x!=None]]

            elif 'minmaxdeals' in supplier_name:
                catalogdf=get_catalog_google_sheets(url).reset_index(drop=True)
                catalogdf=make_first_row_header(catalogdf)

            elif 'gscommoditytrading' in supplier_name:
                catalogdf=get_catalog_google_sheets(url).reset_index(drop=True)
                catalogdf=catalogdf.iloc[9:]

            elif 'epilsonwholesale' in supplier_name:
                catalogdf=get_catalog_google_sheets_2(url, sheet_name='Sheet1')
                catalogdf=catalogdf.iloc[1:]
                catalogdf=make_first_row_header(catalogdf)
                catalogdf=catalogdf[~catalogdf.ASIN.astype(str).str.contains('--')]
                catalogdf=catalogdf.dropna()

            elif supplier_name in ['palletfly','coralport_3m','coralport_avery','coralport_telegram','coralport_wholesale','tjsgroupllc']:
                catalogdf = get_catalog_google_sheets_2(url, sheet_name)
                catalogdf=make_first_row_header(catalogdf)

            elif 'nexdeal' in supplier_name:
                month, year=str(datetime.now().month).zfill(2), str(datetime.now().year)
                url_org=url
                url = url_org.replace('month', month).replace('year', year)
                catalogdf =  get_catalog_google_sheets_3(url)
                if catalogdf.empty: 
                    while True: # keep looping on prev months untill catalog is found
                      try: 
                          month = prev_month # set bcz we decrease month each iteration
                          year = prev_year
                      except: pass
                      # sometimes in start of new month, url is not updated for that month, so try with prev month
                      # if current month is 1, then prev month is 12
                      prev_month='12' if int(month)==1 else  str(int(month)-1).zfill(2)
                      # if current month is 1, then calculate prev year as well
                      prev_year=str(int(year)-1) if int(month)==1 else year 
                      url = url_org.replace('month', prev_month).replace('year', prev_year)
                      catalogdf =  get_catalog_google_sheets_3(url)
                      if not catalogdf.empty:
                          break

            elif 'bajadistributor' in supplier_name:
                headers = {'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.0.0 Safari/537.36',}
                month, year=str(datetime.now().month), str(datetime.now().year)
                url = url.replace('month', month).replace('year', year)
                catalogdf = get_catalog_google_sheets_2(url, sheet_name, headers=headers)
                catalogdf=make_first_row_header(catalogdf)
                if catalogdf.empty: # sometimes in start of new month, url is not updated for that month, so try with prev month
                    url = url.replace(month, str(int(month)-1)).replace('year', year)
                    catalogdf =  get_catalog_google_sheets_3(url)
                    catalogdf=make_first_row_header(catalogdf)

            elif 'dallaswholesale' in supplier_name:
                DWS_columns = ['AMAZON ASIN',	'UPC',	'YOUR PRICE',	'DESCRIPTION',	'BRAND',	'PRICE LISTED ON AMAZON']
                catalogdf=get_catalog_google_sheets(url)
                catalogdf=catalogdf.reset_index(drop=True)
                catalogdf=catalogdf.iloc[1:, :len(DWS_columns)]
                catalogdf.columns = DWS_columns 
                catalogdf = catalogdf[~catalogdf['YOUR PRICE'].astype(str).str.contains('price', case=False, regex=False)]

            elif 'shepher' in supplier_name:
                save_path=f'{tmp_dir}/{supplier_name_org}.xls'
                download_file_urllib(url, save_path)
                # initially file is downloaded as .xls which is old format, so we want .xlsx
                catalogdf=convert_to_xlsx(save_path)
                catalogdf=strip_column_names(catalogdf)
                catalogdf=catalogdf[catalogdf[id_column]!=' ']
                catalogdf[id_column]=catalogdf[id_column].astype(float).astype(int)

            elif supplier_name in ['empiredistribution', 'lvdistribution']:
                catalogdf=get_catalog_google_sheets(url)
                catalogdf=make_first_row_header(catalogdf)

            elif 'cosmetixclub' in supplier_name:
                catalogdf=get_catalog_google_sheets(url)
                catalogdf=catalogdf.iloc[3:]
                catalogdf=make_first_row_header(catalogdf)

            elif 'drachmatrading' in supplier_name:
                catalogdf=get_catalog_google_sheets(url)
                catalogdf=catalogdf[catalogdf['URL LINK'].str.strip().str.startswith('https://')]

            elif 'buywholesaletoday' in supplier_name:
                catalogdf=get_catalog_google_sheets(url)
                catalogdf=catalogdf[catalogdf['ASIN #'].str.contains(r'^[a-zA-Z0-9]{10}$', regex=True)]

            elif supplier_name in ['weinersltd', 'koleimports']:
                catalogdf=get_catalog_google_sheets_4(url)

            else: # default for all others
                catalogdf=get_catalog_google_sheets(url)

            if catalogdf.empty: raise Exception('Catalog Empty')

            catalogs[supplier_name_org]=catalogdf
            catalogdf=strip_column_names(catalogdf)
            try:    catalogdf = catalogdf.loc[:, ~catalogdf.columns.str.contains('Unnamed', case=False, regex=False)]
            except: pass
            catalogdf.to_excel(f'{tmp_dir}/{supplier_name_org}.xlsx', index=False)

        except Exception as e:
            error_catalogs[supplier_name]=e

    print('\n ************************************************* \n')
    print('Error Catalogs: ', error_catalogs)
    print('\n ************************************************* \n')

    return error_catalogs, catalogs

