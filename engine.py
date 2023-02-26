from pathlib import Path
from tqdm import tqdm
from os import walk
import pandas as pd
import string, re, os

tqdm.pandas()
import pdb

from urllib.parse import urlparse
import requests
import csv
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive


class Base:
    """_summary_

    Returns:
        _type_: _description_
    """
    def __init__(self) -> None:
        pass

    def read_multiple_files(self, dir: str):
        all_filenames = next(walk(f"{dir}"), (None, None, []))[2]
        filenames_wanted = [f for f in all_filenames]
        df = pd.DataFrame()
        for fn in filenames_wanted:
            if '.csv' in fn or '.xlsx' in fn: 
                print((f"{dir}/{fn}"))
                tmpdf = (
                    pd.read_csv(f"{dir}/{fn}")
                    if ".csv" in fn
                    else pd.read_excel(f"{dir}/{fn}")
                )
                df = pd.concat([df, tmpdf])
        return df

    def print_chunks(self, ids_list, concat_str, chunk_sz):
        print("Total asins: ", len(ids_list))
        chunks = []
        for i in range(0, len(ids_list), chunk_sz):
            chunk = ids_list[i : i + chunk_sz]
            chunks.append(chunk)

            # with open(f'{self.output_dir}/tmp_{num}.txt ', 'a') as f:
                # f.write(f"{concat_str}".join(chunk)+'\n\n\n\n\n')
            print(f"{concat_str}".join(chunk), "\n\n")





    def clean_price_column(self):
        # hello world
        self.df[self.each_price] = (
            self.df[self.each_price]
            .astype(str)
            .str.replace("$", "", regex=False)
            .str.replace(",", "", regex=False)
            .astype(float)
        )

    def pack_size_extractor(self, product_desc, pack_size_regex):
        product_desc.translate(str.maketrans("", "", string.punctuation))

        pack_size = 1  # default value 1
        for chk in pack_size_regex:
            if sz := re.findall(chk, product_desc):
                pack_size = int(max(sz))

        return pack_size


    def get_pack_size(self, cols=[]):
        pack_size_regex = [
            "pack of ([0-9]+)",
            "([0-9]+) pack",
            "([0-9]+) per pack",
            "([0-9]+)pack",
            "([0-9]+)-pack",
            "([0-9]+) ct pack",
            "([0-9]+) count pack",
            "Multi-Pack \(([0-9]+)\)",
        ]
        if cols:
            self.df[cols[0]] = self.df[cols[0]].astype(str).fillna("1").str.lower().str.strip()
            self.df[cols[1]] = self.df[cols[1]].astype(str).fillna("1").str.lower().str.strip()
            self.df['product_desc']=self.df[cols[0]]+' '+self.df[cols[1]]
        else:
            self.df["Size"] = self.df["Size"].astype(str).fillna("1").str.lower().str.strip()
            self.df["Title"] = self.df["Title"].astype(str).fillna("1").str.lower().str.strip()
            self.df['product_desc'] = self.df["Size"]+' '+self.df["Title"]

        # self.df = self.df.progress_apply(
        #     self.pack_size_extractor, args=(pack_size_regex,), axis=1
        # )
        # self.df["Pack Size"] = self.df["Pack Size"].astype(float)

        self.df['Pack Size'] = self.df["product_desc"].apply(self.pack_size_extractor, args=(pack_size_regex,))

class Helium(Base):
    """_summary_

    Args:
        Base (_type_): _description_

    Returns:
        _type_: _description_
    """

    def __init__(self, helium_dir, id_column="ASIN") -> None:
        self.helium_dir = helium_dir
        self.id_column = "ASIN"
        self.each_price = "Price $"

    def set_helium_df(self):
        self.df = super().read_multiple_files(self.helium_dir)

    def get_helium_df(self):
        return self.df

    def preprocess_helium_df(self):
        self.df["Sales"] = self.df["Sales"].astype(str).str.replace(",", "").astype(float)
        self.df["Revenue"] = self.df["Revenue"].astype(str).str.replace(",", "").astype(float)
        self.df["Review Count"] = self.df["Review Count"].astype(str).str.replace(",", "").astype(float)

class Keepa(Base):
    """_summary_

    Args:
        Base (_type_): _description_

    Returns:
        _type_: _description_
    """

    keepa_cols = [
        "ASIN",
        "URL: Amazon",
        "Amazon: Availability of the Amazon offer",
        "Product Codes: UPC",
        "Size",
        "Title",
        "Sales Rank: 90 days avg.",

    ]

    def __init__(self, keepa_dir, id_column="ASIN") -> None:
        self.keepa_dir = keepa_dir
        self.keepa_asin_code = "ASIN"
        self.keepa_upc_code = "Product Codes: UPC"
        self.id_column = id_column

    def preprocess_upc(self, df, keepa_upc_code):
        df[keepa_upc_code].fillna("", inplace=True)
        df[keepa_upc_code] = df[keepa_upc_code].astype(str).str.split(", ")
        df = df.explode(keepa_upc_code)
        return df

    def set_keepa_df(self):
        self.df = super().read_multiple_files(self.keepa_dir)
        self.df = self.preprocess_upc(self.df, self.keepa_upc_code)
        self.df=self.df[self.keepa_cols].copy()

    def get_keepa_df(self):
        return self.df


class Catalog(Base):
    """_summary_

    Args:
        Base (_type_): _description_

    Returns:
        _type_: _description_
    """

    def __init__(self, supplier_name, catalog_dir, output_dir, catalog_asin_code, catalog_upc_code, catalog_each_price, catalog_product_name, catalog_case_size, catalog_link) -> None:
        self.supplier_name = supplier_name
        self.catalog_dir = catalog_dir
        self.output_dir = output_dir
        self.catalog_asin_code = catalog_asin_code
        self.catalog_upc_code = catalog_upc_code
        self.each_price = catalog_each_price
        self.catalog_case_size = catalog_case_size 
        self.catalog_product_name = catalog_product_name if catalog_product_name.lower() != 'title' else f"{catalog_product_name}_catalog"
        self.id_column = self.catalog_asin_code or self.catalog_upc_code
        self.catalog_link = catalog_link

    def preprocess_df(self):
        self.df=self.df[~((self.df[self.each_price]=='') & (self.df[self.each_price].isnull()))]

    def rename_columns(self, df, columns_list, kw="catalog"):
        rename_dict = dict(zip(columns_list, [f"{x}_{kw}" for x in columns_list]))
        df = df.rename(columns=rename_dict)
        return df

    def get_catalog_google_sheets(self):
        domain = urlparse(self.catalog_link).netloc
        segments = self.catalog_link.rpartition('/')
        link = f"{segments[0]}/export?format=csv"
        file = requests.get(link)
        if file.status_code == 200:
            fileContent = file.content.decode('utf-8')

        reader = csv.reader(fileContent.split('\n'), delimiter=',')
        df=pd.DataFrame(reader)

        new_header = df.iloc[0] #grab the first row for the header
        df = df[1:] #take the data less the header row
        df.columns = new_header
        df.to_excel(f'{self.catalog_dir}/catalog.xlsx')
        return df

    def set_catalog_df(self, df=pd.DataFrame()):
        if not df.empty:
            self.df=df.copy()
        elif self.catalog_link: 
            self.df = self.get_catalog_google_sheets()
        else:
            self.df = super().read_multiple_files(self.catalog_dir)

        self.df = self.rename_columns(self.df, ['Size', 'Title']) # bcz size, title are keepa columns, so if they are in catalog, rename them to _catalog
    
        self.df = self.df.rename(columns={self.each_price: "catalog_each_price"})
        
        self.each_price = "catalog_each_price"
        
        if not self.catalog_case_size: 
            self.catalog_case_size='Case Size'
            self.df[self.catalog_case_size] = 1
        
        self.df[self.id_column] = self.df[self.id_column].astype(str)

    

    def get_catalog_df(self):
        return self.df

    

    def print_ids(self):
        print(",".join(list(self.df[self.id_column].unique())))


class Merged(Base):
    """_summary_

    Args:
        Base (_type_): _description_

    Returns:
        _type_: _description_
    """
    
    def __init__(self, obj_1, obj_2) -> None:
        self.obj_1 = obj_1
        self.obj_2 = obj_2
        self.id_column = "ASIN"

    def set_merged_df(self):
        self.df = pd.merge(
            self.obj_1.df,
            self.obj_2.df,
            how="inner",
            left_on=self.obj_1.id_column,
            right_on=self.obj_2.id_column,
        )
        self.df = self.df.drop_duplicates([self.id_column])

    def get_merged_df(self):
        return self.df

    def set_sales_stats_columns(self):
        self.df["purchase_price"] = self.df["Pack Size"] * self.df["catalog_each_price"]
        self.df["net_profit"] = (
            self.df["Price $"] - self.df["purchase_price"] - self.df["FBA Fees $"]
        )
        self.df["net_profit_%"] = (
            self.df["net_profit"] / self.df["purchase_price"]
        ) * 100

        self.df["expected_sales"] = self.df["Sales"] / self.df["Active Sellers #"]
        self.df["Invest_monthly"] = (
            self.df["purchase_price"] * self.df["expected_sales"]
        )
        self.df["ROI_monthly"] = self.df["net_profit"] * self.df["expected_sales"]
        self.df["ROI_monthly_%"] = (
            self.df["ROI_monthly"] / self.df["Invest_monthly"]
        ) * 100


        


    def apply_soft_filters(self):
        self.df = self.df[self.df["net_profit_%"] >= 0]
        self.df = self.df[
            # ( self.df["Amazon: Availability of the Amazon offer"] == "no Amazon offer exists" ) # keepa
            # & 
            ( self.df["Buy Box"] != "Amazon" )
        ]
        self.df = self.df[(self.df["Ratings"] >= 4.0)]
        self.df = self.df[(self.df["Review Count"] >= 20)]
        self.df = self.df[(self.df["Active Sellers #"] >= 3)]
        self.df = self.df[
            self.df["Size Tier"].isin(["Large Standard-Size", "Small Standard-Size", "Small Oversize"])
        ]  # from helium




class GDrive:
    def __init__(self):
        gauth = GoogleAuth()
        gauth.LocalWebserverAuth() # client_secrets.json need to be in the same directory as the script
        self.drive = GoogleDrive(gauth)

    def get_folder_id(self, parent_id, kw):
        fileList = self.drive.ListFile({'q': f"'{parent_id}' in parents and trashed=false"}).GetList()
        df=pd.DataFrame(fileList)
        # req_folder_id=df[df.title.str.contains(kw, case=False, na=False)].id.item()
        req_folder_id=df[df.title.str.lower() == kw.lower()].id.item()
        return req_folder_id

    def find_gdrive_folder_id(self, tree, folder_id='root'):
        # pdb.set_trace()
        folder_id  = self.get_folder_id(folder_id, tree[0])
        tree.remove(tree[0])
        if tree: folder_id=self.find_gdrive_folder_id(tree, folder_id)
        else:    return folder_id
        return folder_id

    def download_files(self, gdrive_folder_id, local_folder_path):
        fileList = self.drive.ListFile({'q': f"'{gdrive_folder_id}' in parents and trashed=false"}).GetList()
        df=pd.DataFrame(fileList)
        Path(local_folder_path).mkdir(parents=True, exist_ok=True)
        for _, row in df.iterrows():
            tmp_file = self.drive.CreateFile({'id': row.id})
            tmp_file.GetContentFile(f'{local_folder_path}/{row.title}')  # Save Drive file as a local file
        return True

    def create_folder(self, parent_folder_id, folder_name):
        # Create folder
        folder_metadata = {'title' : folder_name, 'mimeType' : 'application/vnd.google-apps.folder', 'parents':[{'id':parent_folder_id}]}
        folder = self.drive.CreateFile(folder_metadata)
        folder.Upload()
        return folder.get('id')

    def upload_file(self, folder_id, file_path):
        # Upload file to folder
        file = self.drive.CreateFile({"parents": [{"kind": "drive#fileLink", "id": folder_id}]})
        file['title'] = os.path.basename(file_path)
        file.SetContentFile(file_path)
        file.Upload()
        return file.get('id')

    def update_file_by_id(self, file_id, file_path):
        try:
            # replace file in folder
            file1 = self.drive.CreateFile({'id':file_id})
            file1.SetContentFile(file_path)
            file1.Upload()
            return True 
        except Exception as e:
            print('Error in update_file_by_id: ', e)

    def delete_by_name(self, tree):
        try:
            # pdb.set_trace()
            folder_id=self.find_gdrive_folder_id(tree=tree, folder_id='root')
            is_deleted = self.delete_by_id(folder_id)
            return True
        except Exception as e:
            print(e)
            return False

    def delete_by_id(self, _id):
        try:
            file2del = self.drive.CreateFile({'id': _id})

            file2del.Delete() 

            # self.drive.files().delete(fileId=_id).execute()
            return True
        except Exception as e:
            print(e)
            return False

    def find_file_by_name(self, tree):
        try:
            folder_id=self.find_gdrive_folder_id(tree=tree[:-1], folder_id='root')

            file_list = self.drive.ListFile({'q': f"'{folder_id}' in parents and  trashed=False"}).GetList()

            for x in range(len(file_list)):
                if file_list[x]['title'] == tree[-1]:
                    file_id = file_list[x]['id']
            
            return file_id
        except Exception as e:
            print('Error in find_file_by_name: ', e)

