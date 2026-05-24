import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# 1. Setup Streamlit Page
st.set_page_config(page_title="Chrome Sector RS", layout="wide")
st.title("🚀 Theme Tracker")

st.markdown(
    """
    <style>
    /* Adjusts the sidebar drawer structural container width */
    [data-testid="stSidebar"] {
        min-width: 240px !important;
        max-width: 240px !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# 2. Cleaned Industry Database (Preserved as requested)
INDUSTRIES = {
    '3D printing': ['XMTR', 'VELO', 'DDD', 'PRLB', 'MTLS', 'SSYS', 'NNDM'],
    'Crypto': ['MSTR', 'CRCL', 'COIN', 'IBIT'],
    'Nuclear': ['URA', 'NLR', 'CEG', 'CCJ', 'OKLO', 'UUUU', 'SMR', 'LEU'],
    'MAG7': ['AAPL', 'GOOGL', 'NVDA', 'META', 'MSFT', 'AMZN', 'TSLA'],
    'ETF': ['XLK', 'XLF', 'XLE', 'XLP', 'XLU', 'XLI', 'XLY', 'XLV', 'XLC', 'XLB'],
    'SPACE': ['UFO', 'VSAT', 'RKLB', 'SATL', 'RDW', 'LUNR', 'BKSY', 'PL', 'IRDM', 'SATS', 'GSAT', 'ASTS', 'ARKX', 'FLY', 'HON', 'SPCE', 'AVAV', 'KRMN', 'SIDU'],
    'CATHIE WOOD': ['ARKG', 'ARKK', 'ARKQ', 'ARKW', 'ARKF', 'ARKX'],
    'CHINA': ['FUTU', 'LI', 'KWEB', 'XPEV', 'NIO', 'PDD', 'BIDU', 'JD', 'BABA'],
    'DATA CENTER / AI HOSTING': ['WGMI', 'CRWV', 'NBIS', 'IREN', 'WULF', 'CORZ', 'CIFR', 'HUT', 'BTDR'],
    'ENERGY SOLAR': ['TAN', 'SEDG', 'ENPH', 'FSLR', 'ARRY', 'SHLS', 'CSIQ', 'RUN', 'DQ'],
    'COML SVCS-ADVRTSNG': ['OMC', 'DJT'],
    'AEROSPACE/DEFENSE': ['ITA', 'RTX', 'LMT', 'HON', 'BA', 'GD', 'NOC', 'TDG', 'LHX', 'HWM', 'AXON', 'HEI', 'LDOS', 'TDY', 'TXT', 'FTAI', 'CW', 'BWXT', 'HII', 'CR', 'DRS', 'LOAR', 'AVAV', 'HXL', 'KTOS', 'MIR', 'OSIS', 'AIR', 'MRCY'],
    'AGRICULTURAL OPRTIONS': ['ADM', 'BG', 'PPC', 'CALM', 'SEB'],
    'TRNSPRT-AIR FREIGHT': ['UPS', 'FDX'],
    'TRANSPORTATION-SVCS': ['DASH', 'EXPD', 'CHRW', 'CART', 'GXO', 'HUBG', 'UBER', 'PFGC', 'SARO', 'VNT', 'VRRM', 'CAAP'],
    'TRNSPRTTIN-AIRLNE': ['JETS', 'DAL', 'UAL', 'LUV', 'AAL', 'ALK', 'CPA', 'SKYW'],
    'ENERGY-ALT/OTHER': ['BIP', 'TLN', 'CWEN', 'BEPC'],
    'MINING-METAL ORES': ['AA', 'SCCO', 'FCX', 'CCJ', 'CRS', 'ATI', 'MP', 'TECK'],
    'APPAREL-SHOES & REL': ['NKE', 'DECK', 'ONON', 'RL', 'BIRK', 'CROX', 'LEVI', 'VFC', 'GIL', 'PVH', 'COLM', 'KTB', 'SHOO'],
    'RETAIL-APPRL/SHOES/ACC': ['TJX', 'ROST', 'BURL', 'TPR', 'GAP', 'ANF', 'BBWI', 'CPRI', 'BOOT', 'AEO', 'URBN', 'CRI', 'BKE', 'VSCO'],
    'AUTO/TRCK-ORGNL EQP': ['ITW', 'CMI', 'APTV', 'ITT', 'DCI', 'ALSN', 'ALV', 'GNTX', 'LEA', 'BC', 'ATMU', 'VC', 'BWA'],
    'AUTO/TRCK-RPLC PRTS': ['LKQ', 'DORM', 'AAP'],
    'BEVERAGES-ALCOHOLIC': ['STZ', 'TAP', 'SAM'],
    'BEV-NON-ALCOHOLIC': ['KO', 'MNST', 'CCEP', 'COKE', 'BRBR', 'CELH', 'FIZZ'],
    'MEDICAL-BIOMED/BTH': ['BNTX', 'AMGN', 'GILD', 'MRNA', 'ILMN', 'SMMT', 'PCVX', 'BMRN', 'TECH', 'NUVL', 'ELAN', 'HALO', 'RNA', 'KRYS', 'ADMA', 'BBIO', 'IMVT', 'ACLX', 'AXSM', 'CRSP', 'DNLI', 'ALVO', 'APGE', 'DYN', 'RYTM', 'KYMR', 'EWTX', 'PTGX', 'TWST', 'TXG', 'CGON', 'JANX', 'ARWR', 'VERA', 'NVAX', 'CLDX'],
    'MEDIA-RADIO/TV': ['FOX', 'SIRI', 'NXST', 'TGNA'],
    'TELCOM-SVC-CBL/SAT': ['CMCSA', 'CHTR'],
    'LEISRE-GAMNG/EQUIP': ['FLUT', 'LVS', 'MGM', 'WYNN', 'CZR', 'LNW', 'BYD', 'RSI', 'DKNG', 'CHDN', 'PENN'],
    'CHEMICALS-AG': ['NTR', 'CTVA', 'CF', 'MOS', 'FMC', 'SMG'],
    'CHEMICALS-BASIC': ['DD', 'ESI', 'AVNT', 'HUN', 'IOSP', 'DOW', 'LYB', 'WLK', 'AVTR', 'CE', 'EMN', 'CC'],
    'CHEMICALS-SPECIALTY': ['LIN', 'ECL', 'APD', 'ALB', 'CHX', 'CBT', 'NEU', 'KWR', 'HWKN', 'MTX', 'TROX', 'OLN', 'FUL', 'WDFC', 'AZZ', 'UFPT'],
    'ENERGY COAL': ['HCC', 'BTU', 'ARLP', 'AMR'],
    'MEDIA-DIVERSIFIED': ['WMG', 'SPOT', 'LYV', 'DIS', 'WBD'],
    'COMPTER-NETWRKING': ['ANET', 'CSCO', 'CALX'],
    'COMPTR-DATA STRGE': ['DRAM', 'WDC', 'STX', 'MU', 'SNDK', 'SIMO'],
    'CMP-HRDWRE/PERIP': ['DELL', 'HPQ', 'SMCI', 'HPE', 'ZBRA', 'NATL'],
    'CONTAINERS/PACKAGING': ['SW', 'BALL', 'PKG', 'AVY', 'AMCR', 'OC', 'CCK', 'ATR', 'GPK', 'SLGN', 'SON', 'SEE', 'GEF', 'OI'],
    'OIL&GAS-DRILLING': ['SLB', 'BKR', 'NE', 'VAL', 'HP', 'SDRL'],
    'BLDG-CMENT/CNCRT': ['CRH', 'MLM', 'VMC', 'EXP', 'KNF', 'USLM'],
    'CMPTER-TECH SRVCS': ['PAYX', 'MSCI', 'VRSK', 'TYL', 'GDDY', 'J', 'FDS', 'AKAM', 'DBX', 'EXLS', 'KD', 'MARA', 'EEFT', 'DXC', 'CORZ', 'AVPT', 'ACN', 'CTSH', 'CDW', 'CACI', 'PSN', 'EPAM', 'DOX', 'KBR', 'GLOB', 'NSIT', 'SAIC', 'ASGN'],
    'RETAIL-DPRTMNT STRS': ['DDS', 'M', 'KSS'],
    'RETAIL-DISCNT&VARI': ['DG', 'DLTR', 'FIVE', 'OLLI'],
    'RETAIL-DRUG STORES': ['CVS', 'UNH', 'ELV', 'HUM'],
    'UTILITY-ELCTRIC PWR': ['NEE', 'SO', 'CEG', 'DUK', 'AEP', 'SRE', 'D', 'VST', 'PEG', 'PCG', 'EXC', 'XEL', 'ED', 'EIX', 'WEC', 'ETR', 'DTE', 'FE', 'PPL', 'AEE', 'ES', 'CMS', 'NRG', 'CNP', 'LNT', 'EVRG', 'AES', 'PNW', 'OGE', 'IDA', 'POR', 'ORA', 'BKH', 'TXNM', 'NWE', 'MGEE'],
    'ELECTRICAL POWER/EQPMT': ['ETN', 'GEV', 'AME', 'ROK', 'HUBB', 'RRX', 'GNRC', 'AYI', 'BDC', 'ENS', 'FLNC', 'SMR', 'ATKR', 'PBW', 'POWL', 'VICR', 'BE', 'ENVX'],
    'TELCOM-FIBR OPTCS': ['XTL', 'AAOI', 'COHR', 'CIEN', 'FN', 'LITE', 'AXTI'],
    'ELEC-PARTS': ['APH', 'GLW', 'NVT', 'CAMT', 'TEL'],
    'ELEC-SCNTIFIC/MSRNG': ['PH', 'EMR', 'KEYS', 'FTV', 'CGNX', 'NOVT', 'ST', 'NXT', 'ITRI', 'ESE', 'SXI', 'MTRN'],
    'ELEC-SEMICNDCTR EQP': ['ASML', 'KLAC', 'AMAT', 'LRCX', 'ONTO', 'NVMI', 'TER', 'AEIS', 'MKSI', 'ENTG', 'ACLS', 'AEHR'],
    'ELEC-CONTRACT MFG': ['CLS', 'SOLS', 'VRT', 'FLEX', 'PLXS', 'JBL', 'SANM', 'TTMI'],
    'ELEC-MISC PRODUCTS': ['OLED', 'LFUS', 'VSH'],
    'WHOLESALE-ELECT': ['SNX', 'ARW', 'AVT', 'REZI', 'GWW', 'FAST', 'FERG', 'GPC', 'POOL', 'AIT', 'WCC', 'MSM', 'UGI'],
    'RETAIL-CNSMR ELEC': ['BBY', 'GME'],
    'CONSUMER PROD-ELEC': ['SN', 'ROKU', 'WHR', 'SPB', 'AAPL'],
    'BLDG-HEAVY CONSTR': ['PWR', 'EME', 'FIX', 'ACM', 'TTEK', 'MTZ', 'APG', 'FLR', 'DY', 'STRL', 'ROAD', 'GVA', 'PRIM'],
    'BLDG-RSIDNT/COMML': ['ITB', 'BLD', 'IBP', 'EXPO', 'IESC', 'DHI', 'LEN', 'NVR', 'PHM', 'TOL', 'MTH', 'TMHC', 'KBH', 'SKY', 'MHO', 'TPH', 'FTDR', 'GRBK', 'DFH', 'CCS', 'LGIH'],
    'BLDG-MBILE/MFG & RV': ['CVCO', 'PATK'],
    'POLLUTION CONTROL': ['WM', 'RSG', 'CLH', 'CWST'],
    'COMML SVCS-LEASING': ['URI', 'AER', 'UHAL', 'WSC', 'R', 'AL', 'HRI', 'WD', 'CAR', 'MGRC', 'PRG'],
    'FINANCE-CARD/PMTPR': ['AXP', 'SYF', 'AFRM', 'FCFS', 'SLM', 'V', 'MA', 'PYPL', 'GPN', 'CPAY', 'FOUR', 'WEX', 'PAY', 'RELY', 'SOFI'],
    'FINANCE-CONS LOAN': ['RKT', 'OMF', 'ENVA', 'NNI'],
    'FINANCE-CMRCL LOAN': ['OBDC', 'PFSI', 'CACC'],
    'FINANCE-BLANK CHECK': ['BCSF', 'LOCL', 'MNTN', 'MSDL', 'NCDL', 'OKLO', 'PSBD', 'RMI', 'SBXD'],
    'FINANCIAL SVC-SPEC': ['BLK', 'SPGI', 'MCO', 'EFX', 'TRU', 'ICLR', 'BAH', 'MEDP', 'CRL', 'FCN', 'MMS', 'CBZ', 'NSP', 'ICFI', 'EVH', 'FA'],
    'WHOLESALE-FOOD': ['SYY', 'USFD'],
    'RETAIL-SPR/MINI MKTS': ['KR', 'SFM', 'ACI', 'TBBB', 'CASY'],
    'FOOD-PACKAGED': ['KHC', 'GIS', 'CAG', 'SMPL', 'MDLZ', 'KDP', 'HSY', 'CPB', 'SJM', 'POST', 'LANC', 'FLO', 'NOMD', 'UTZ'],
    'FOOD-MEAT PRODUCTS': ['TSN', 'HRL'],
    'FOOD-MISC PREP': ['PEP', 'IFF', 'MKC', 'LW', 'INGR', 'DAR', 'BCPC', 'ASH', 'JJSF', 'SXT', 'TR'],
    'FOOD-CONFECTIONERY': ['FRPT', 'BROS'],
    'BLDG-WOOD PRDS': ['UFPI', 'LPX', 'TREX'],
    'UTILITY-GAS DSTRIBTN': ['TRGP', 'CQP', 'ATO', 'NI', 'MDU', 'BIPC', 'SWX', 'NJR', 'OGS', 'SR', 'CPK', 'EE'],
    'RTAIL-HME FRNSHNGS': ['MBC', 'WSM', 'W', 'RH'],
    'RETL WHSLE BLDG PRDS': ['HD', 'LOW', 'BLDR', 'FND', 'CNM', 'BCC'],
    'MEDCAL-HOSPITALS': ['HCA', 'THC', 'UHS'],
    'MED-LONG-TRM CARE': ['CHE', 'PACS', 'SEM', 'SGRY', 'ARDT', 'ENSG', 'ADUS'],
    'MEDICAL-SERVICES': ['DVA', 'SOLV', 'EHC', 'ACHC', 'RDNT', 'OPCH', 'HIMS', 'GH', 'BTSG', 'CON', 'AZTA', 'TDOC'],
    'LEISURE-LODGING': ['MAR', 'HLT', 'RCL', 'CCL', 'VIK', 'H', 'NCLH', 'MTN', 'WH', 'CHH', 'RRR', 'TNL', 'VAC'],
    'COSMETICS/PERSNL CRE': ['PG', 'CL', 'KMB', 'KVUE', 'EL', 'CHD', 'CLX', 'ELF', 'IPAR'],
    'SOAP & CLNG PREPARAT': ['REYN', 'ENR'],
    'DVRSIFIED OPRTIONS': ['MMM', 'RLX', 'WMS', 'AWI', 'BRC', 'YETI', 'LCII'],
    'MCHNRY-GEN INDSTRL': ['GE', 'TT', 'CARR', 'JCI', 'IR', 'XYL', 'DOV', 'LII', 'PNR', 'IEX', 'GGG', 'NDSN', 'LECO', 'WWD', 'AAON', 'FLS', 'MIDD', 'MOD', 'WTS', 'BMI', 'ZWS', 'ESAB', 'TKR', 'GTLS', 'GTES', 'FELE', 'KAI', 'MWA', 'NPO', 'CXT', 'OII', 'SYM'],
    'CHEMICALS-PAINTS': ['SHW', 'PPG', 'RPM', 'AXTA'],
    'COMPTER SFTWR-SCRITY': ['BUG', 'FTNT', 'PANW', 'CRWD', 'CHKP', 'RBRK', 'RPD', 'OKTA', 'ZS', 'TENB'],
    'COMPTER SFTWR-ENTR': ['IGV', 'TWLO', 'MSFT', 'ORCL', 'CRM', 'IBM', 'NOW', 'ADP', 'DOCN', 'PLTR', 'ADSK', 'ROP', 'TEAM', 'SNOW', 'VEEV', 'HUBS', 'PTC', 'MDB', 'MANH', 'TOST', 'MNDY', 'WDAY', 'SSNC', 'GWRE', 'BSY', 'PEGA', 'QTWO', 'APPF', 'BOX', 'WK'],
    'COMPTER SFTWR-DSGN': ['ADBE', 'INTU', 'SNPS', 'CDNS', 'IOT', 'DT', 'TRMB', 'WIX'],
    'CMPTER SFTWR-FINCL': ['FICO', 'FIS', 'NU', 'SHOP'],
    'CMP SFTWR-GAMING': ['EA', 'TTWO', 'RBLX'],
    'CMP SFTWR-DBASE': ['DDOG', 'MDB', 'ORCL', 'ESTC'],
    'COMPTER SFTWR-DSKTP': ['ZM', 'SNAP', 'Z'],
    'CMPTR SFTWR-MDCL': ['APP', 'HQY'],
    'INTERNET-CONTENT': ['GOOGL', 'META', 'NFLX', 'SPOT', 'PINS', 'RDDT', 'MMYT', 'MTCH', 'IAC', 'YELP', 'GRND'],
    'INTRNT-NETWK SLTNS': ['IT', 'MSTR', 'CSGP', 'VRSN', 'UPST', 'BRZE', 'CARG', 'NET', 'VLTO'],
    'INSURANCE-BROKERS': ['AON', 'AJG', 'WTW', 'BRO', 'RYAN', 'CRVL', 'GSHD'],
    'OIL&GAS INTEGRATED': ['XOM', 'CVX', 'OXY'],
    'OIL&GAS-U S EXPL PRO': ['XOP', 'COP', 'EOG', 'FANG', 'DVN', 'EQT', 'EXE', 'CTRA', 'PR', 'OVV', 'APA', 'CHRD', 'MTDR', 'NFG', 'CNX', 'CRC', 'CRGY', 'AR', 'RRC', 'MUR', 'MGY', 'SM', 'NOG', 'CRK', 'GPOR', 'XPRO'],
    'OIL&GAS-ROYALTY TRUST': ['VNOM', 'HESM', 'BSM'],
    'RETAIL-INTERNET': ['AMZN', 'MELI', 'CPNG', 'LULU', 'EBAY', 'CHWY', 'GLBE', 'ETSY', 'ACVA'],
    'FIN-INVEST BNK/BKRS': ['GS', 'SCHW', 'ICE', 'CME', 'IBKR', 'BK', 'COIN', 'NDAQ', 'TW', 'STT', 'CBOE', 'HOOD', 'LPLA', 'JEF', 'HLI', 'MKTX', 'XP', 'EVR', 'FRHC', 'PJT', 'MC', 'PIPR', 'VIRT', 'LAZ', 'SNEX'],
    'FNCE-INVSMNT MGT': ['BX', 'MS', 'KKR', 'BN', 'APO', 'ARES', 'OWL', 'RJF', 'TROW', 'TPG', 'PFG', 'BAM', 'NTRS', 'CRBG', 'CG', 'MORN', 'ARCC', 'BEN', 'SF', 'HLNE', 'SEIC', 'IVZ', 'STEP', 'JHG', 'FSK', 'AMG', 'CNS', 'MAIN', 'GBDC', 'AB', 'VCTR', 'APAM', 'HTGC', 'IFS', 'FHI', 'GCMG', 'AMP'],
    'FINANC-PBL INV FDEQT': ['TPL', 'BXSL'],
    'INSURANCE-LIFE': ['PRU', 'EQH', 'PRI', 'VOYA', 'JXN', 'LNC', 'BHF', 'PRVA'],
    'BANKS-MONEY CNTR': ['JPM', 'BAC', 'WFC', 'C', 'COF'],
    'BANKS-FOREIGN': ['UBS', 'BAP'],
    'BANKS-SUPR RGIONAL': ['PNC', 'HBAN', 'RF', 'CFG', 'KEY', 'ZION', 'FITB', 'TFC', 'MTB', 'ALLY', 'WAL'],
    'BANKS-WST/STHWST': ['BOKF', 'ONB', 'TCBI', 'WAFD', 'PRK', 'BKU', 'IBOC', 'BANF', 'UCB', 'AUB', 'FIBK', 'CATY', 'FHB', 'BOH', 'CVBF'],
    'BANKS-SOUTHEAST': ['KBE', 'CADE', 'FNB', 'FBK', 'SNV', 'HOMB', 'OZK', 'ABCB'],
    'BANKS-MIDWEST': ['KRE', 'FFIN', 'UMBF', 'ASB', 'FULT', 'CBU', 'SFNC', 'FRME', 'NBTB', 'CBSH', 'COLB', 'GBCI', 'UBSI', 'HWC', 'TOWN'],
    'BANKS-NORTHEAST': ['IAT', 'FCNCA', 'EWBC', 'FHN', 'CFR', 'PNFP', 'SSB', 'WTFC', 'BPOP', 'PB', 'WU', 'EBC', 'FBP', 'TBBK'],
    'FINANC-SVINGS & LO': ['WBS', 'NYCB', 'TFSL', 'WSFS', 'PFS'],
    'MED-MANAGED CARE': ['UNH', 'ELV', 'CI', 'CNC', 'HUM', 'MOH', 'OSCR', 'ALHC'],
    'TRANSPORTATION-SHIP': ['KEX', 'FRO', 'MATX', 'GLNG', 'STNG', 'TDW', 'INSW', 'SBLK', 'GOGL', 'ZIM', 'TNK'],
    'MDCAL-WHLSLE DRG': ['MCK', 'COR', 'CAH', 'HSIC'],
    'MEDICAL-PRODUCTS': ['TMO', 'ABT', 'DHR', 'A', 'IDXX', 'RMD', 'MTD', 'RVTY', 'EXAS', 'BRKR', 'QGEN', 'BIO', 'GMEN', 'LNTH', 'MASI', 'GKOS', 'BLCO', 'MMSI'],
    'MEDICAL-SYSTEMS/EQP': ['IHI', 'ISRG', 'SYK', 'BSX', 'MDT', 'BDX', 'GEHC', 'EW', 'DXCM', 'STE', 'WST', 'COO', 'ZBH', 'WAT', 'HOLX', 'BAX', 'ALGN', 'PODD', 'NTRA', 'TFX', 'PEN', 'INSP'],
    'METAL PROC & FABRICA': ['RBC', 'MLI', 'VMI', 'ROCK'],
    'CMML SVCS-CNSLTNG': ['TNET', 'LOPE', 'CNXC', 'ABM', 'RCM', 'LAUR', 'QXO', 'G'],
    'AUTO MANUFACTURERS': ['TSLA', 'GM', 'F', 'RIVN'],
    'TRNSPRT-EQP MFG': ['OSK', 'HOG', 'WAB', 'TEX', 'TRN', 'ALG'],
    'LEISRE-MVIES & REL': ['DIS', 'LYV', 'FWONA', 'TKO', 'MSGS', 'FUN', 'CNK', 'PRKS', 'MANU', 'BATRA'],
    'INSRNCE-DIVRSIFIED': ['PGR', 'AFL', 'MET', 'ACGL', 'HIG', 'CINF', 'RGA', 'CNA', 'UNM', 'KNSL', 'GL', 'RLI', 'AXS', 'BWIN', 'ACT', 'FG', 'ESGR', 'WTM', 'CNO'],
    'OFFICE SUPPLIES MFG': ['HNI', 'MLKN', 'ACCO'],
    'OIL&GAS-TRNSPRT/PIP': ['EPD', 'WMB', 'ET', 'OKE', 'KMI', 'MPLX', 'LNG', 'WES', 'PAA', 'DTM', 'KNTK', 'AM', 'ENLC', 'SOBO', 'PAGP', 'DKL'],
    'OIL&GAS-RFING/MKT': ['PSX', 'MPC', 'VLO', 'DINO', 'IEP', 'PBF', 'CVI', 'SUN'],
    'OIL&GAS-FIELD SERVIC': ['HAL', 'FIT', 'WFRD', 'NOV', 'WHD', 'AROC', 'LBRT', 'USAC', 'KGS', 'AESI'],
    'LEISURE-SERVICES': ['CTAS', 'ROL', 'SCI', 'HRB', 'PLNT', 'LTH', 'VVV', 'GHC', 'UNF', 'LRN', 'ATGE', 'DRVN', 'STRA'],
    'CONSUMR PROD-SPECI': ['MSA', 'HAS', 'AS', 'MAT', 'THO', 'PII', 'GOLF', 'HAYW', 'VSTO', 'SIG'],
    'CMP SFTWR-SPC-ENTR': ['TTD', 'MGNI', 'PUBM'],
    'MEDICAL-ETHICAL DRGS': ['NVO', 'LLY', 'JNJ', 'ABBV', 'MRK', 'PFE', 'VRTX', 'REGN', 'BMY', 'ZTS', 'ALNY', 'BIIB', 'RPRX', 'UTHR', 'VTRS', 'INCY', 'INSM', 'SRPT', 'NBIX', 'CTLT', 'ROIV', 'ITCI', 'RGEN', 'VKTX', 'EXEL', 'JAZZ', 'CYTK', 'IONS', 'BHVN', 'RARE', 'CORT', 'MDGL', 'OGN', 'ALKS', 'CRNX', 'TGTX', 'PHB', 'PRGO', 'APLS', 'RVMD'],
    'MINING-GLD/SILVR/GMS': ['NEM', 'RGLD'],
    'INSRNCE-PRP/CAS/TITL': ['BRK.B', 'CB', 'TRV', 'ALL', 'AIG', 'ERIE', 'WRB', 'MKL', 'L', 'EG', 'RNR', 'AFG', 'AIZ', 'MTG', 'SIGI', 'THG', 'KMPR', 'HGTY', 'MCY', 'NMIH', 'PLMR', 'SPNT', 'FNF', 'ORI', 'ESNT', 'FAF', 'RDN', 'AGO'],
    'MEDIA-BOOKS': ['WLY', 'SCHL', 'NYT'],
    'MEDIA-NEWSPAPERS': ['NWS', 'NYT'],
    'PAPER & PAPER PRODUC': ['IP', 'SLVM'],
    'TRANSPORTATION-RAIL': ['UNP', 'CSX', 'NSC', 'GATX'],
    'REAL STATE DVLPMT/OPS': ['CBRE', 'JLL', 'HHH', 'HGV', 'JOE', 'CWK', 'NMRK', 'EXPI'],
    'FINANCE-REIT': ['HASI', 'ESBA'],
    'RETAIL-MJR DSC CHNS': ['WMT', 'COST', 'TGT', 'BJ', 'PSMT'],
    'RETAIL/WHLSLE-AUTO': ['CVNA', 'KMX', 'PAG', 'MUSA', 'LAD', 'AN', 'GPI', 'ABG', 'RUSHA'],
    'RETAIL/WSL-AUTO PRT': ['ORLY', 'AZO'],
    'RETAIL-SPECIALTY': ['MUSA', 'CASY', 'HZO', 'COST', 'BJ', 'ARKO', 'WMT', 'PSMT', 'TBBB', 'TGT', 'DKS', 'FIVE', 'BOBS', 'BBW', 'WINA', 'GME', 'MNSO', 'BBY', 'ULTA', 'EVGO', 'BWMX', 'OLLI', 'DLTR', 'RH', 'ASO', 'WSM', 'WOOF', 'DG', 'BBWI', 'SVV', 'SBH', 'BNED', 'ARHS', 'TSCO', 'EYE'],
    'RETAIL-RESTAURANTS': ['MCD', 'SBUX', 'CMG', 'YUM', 'QSR', 'DRI', 'YUMC', 'CAVA', 'DPZ', 'WING', 'TXRH', 'ARMK', 'SHAK', 'SG', 'EAT', 'WEN', 'CAKE'],
    'TELECOM SVCS-FOREIGN': ['FYBR', 'CCOI', 'LBTYA'],
    'TELCOM-INFRASTR': ['SATS', 'ASTS', 'IRDM'],
    'STEEL-PRODUCERS': ['NWPX', 'PKX', 'NUE', 'STLD', 'WS', 'WS', 'RS', 'ASTL', 'CLF', 'GGB', 'CMC', 'RIO', 'TX', 'MTUS', 'MT', 'HCC', 'MSB', 'VALE', 'SID'],
    'TELCOM-CONS PROD': ['MSI', 'GRMN', 'UI'],
    'TEXTILES': ['AIN', 'CULP', 'UFI'],
    'TOBACCO': ['PM', 'MO'],
    'BLDG-HAND TOOLS': ['SWK', 'SNA'],
    'TRNSPORTATION-TRCK': ['ODFL', 'JBHT', 'XPO', 'SAIA', 'KNX', 'LSTR', 'SNDR', 'ARCB', 'WERN'],
    'MACHINERY-FARM': ['DE', 'CNH', 'TTC', 'AGCO', 'SITE', 'FSS', 'ACA'],
    'MCHNRY-CNSTR/MNG': ['CAT', 'PCAR', 'LGN'],
    'UTILITY-WATER SUPPLY': ['AWK', 'WTRG', 'AWR', 'CWT'],
    'TELCOM SVC-WIRLES': ['TMUS', 'VZ', 'T', 'LBRDA', 'USM', 'TIGO', 'TDS'],
    'ELEC-SEMICON FBLSS': ['ARM', 'NVDA', 'AVGO', 'AMD', 'QCOM', 'ADI', 'MRVL', 'NXPI', 'MPWR', 'MCHP', 'ON', 'SWKS', 'QRVO', 'ALAB', 'CRDO', 'MTSI', 'LSCC', 'CRUS', 'PI', 'RMBS', 'SITM', 'ALGM', 'SLAB', 'POWI', 'IPGP', 'SMTC', 'DIOD', 'SYNA', 'AMBA'],
    'ELEC-SEMICON MFG': ['TSM', 'TXN', 'INTC', 'GFS', 'AMKR', 'TSEM', 'FORM', 'STM']
}

# Cleaned Known Stocks List Reference Array
KNOWN_STOCKS = [
    'LGN', 'IESC', 'AEHR', 'ACLS', 'MKSI', 'SMTC', 'AMKR', 'LSCC', 'DIOD', 'POWI', 'AA', 'ABBV', 'ALAB', 'AMGN', 'APO', 'BOTZ', 'CRCL', 'CRWV', 'D', 'DRAM', 'DUK', 'EEM', 'EWJ', 'EXC', 'FIGR', 
    'GEV', 'GILD', 'GXC', 'HON', 'JEF', 'JKS', 'KMI', 'KRMN', 'LIN', 'MNST', 'NASA', 'NEM', 'NTR', 'NTAP', 'OR', 
    'OWL', 'Q', 'QQQ', 'RNG', 'RKT', 'SCCO', 'SHLD', 'SO', 'SOLS', 'SPMO', 'SPY', 'SPHB', 'TSEM', 'UNP', 'VTV', 
    'VUG', 'WGMI', 'WMB', 'XEL', 'XMAG', 'XYZ', 'ZIM','VICR', 'SLX', 'CBOE', 'SIMO', 'FLEX', 'POWL', 'VLO', 'DOCN', 
    'IYZ', 'LNG', 'AAOI', 'AXTI', 'TSEM', 'USO', 'JNJ', 
    'HP', 'GLD', 'ALB', 'BUG', 'BX', 'DOW', 'VZ', 'REMX', 'GDX', 'SIL', 'VEEV', 'SNDK', 'TLT', 'APH', 'ARM', 'FANG', 
    'NBIS', 'NVT', 'OXY', 'FORM', 'IBIT', 'QTUM', 'IAI', 'KWEB', 'IHI', 'UFO', 'ITA', 'IYT', 'CVS', 'HUM', 'NEE', 
    'HPE', 'PLAB', 'INOD', 'TTMI', 'CCJ', 'BE', 'SLV', 'PICK', 'COPX', 'MAR', 'XAR', 'VSCO', 'GLW', 'ANF', 'AEO', 
    'AEP', 'GH', 'SANM', 'ROK', 'PSN', 'IAT', 'HROW', 'PL', 'AVAV', 'CIEN', 'COHR', 'NU', 'WULF', 'IREN', 'CIFR', 
    'RDW', 'PH', 'LITE', 'ACHR', 'CACI', 'CRS', 'URA', 'NVO', 'NLR', 'ITB', 'MVST', 'EOSE', 'APP', 'RKLB', 'ASTS', 
    'IONQ', 'RMBS', 'RTX', 'NOC', 'LMT', 'HON', 'ONDS', 'CLS', 'LEU', 'VRT', 'VST', 'NRG', 'CEG', 'SMCI', 'CRDO', 
    'SOFI', 'XLP', 'XLE', 'HIMS', 'HOOD', 'GEV', 'XLV', 'HACK', 'XOP', 'CIBR', 'ICLN', 'XLB', 'XLU', 'XLRE', 'IGV', 
    'XLF', 'IPAY', 'XLC', 'XLI', 'KRE', 'XLK', 'CLOU', 'KBE', 'XME', 'XTL', 'JETS', 'SMH', 'XLY', 'XHB', 
    'BLOK', 'XBI', 'XRT', 'MJ', 'META', 'MSFT', 'AAPL', 'AMZN', 'GOOGL', 'NVDA', 'TSLA', 'ARKX', 'ARKQ', 'ARKF', 
    'ARKW', 'ARKK', 'ARKG', 'CCL', 'RCL', 'UAL', 'BA', 'DAL', 'NCLH', 'AAL', 'LUV', 'PINS', 'SNAP', 
    'IBKR', 'SCHW', 'JPM', 'MS', 'GS', 'BAC', 'WFC', 'SPGI', 'BLK', 'NDAQ', 'C', 'LI', 'BIDU', 'NIO', 'XPEV', 
    'BABA', 'PDD', 'JD', 'DQ', 'JKS', 'ENPH', 'FSLR', 'TAN', 'SEDG', 'CSIQ', 'SPWR', 'RUN', 'PBW', 'CLX', 'PG', 
    'EL', 'LULU', 'SBUX', 'NKE', 'MELI', 'EBAY', 'FDX', 'UPS', 'SE', 'JMIA', 'ETSY', 'SHOP', 
    'Z', 'OPEN', 'CHWY', 'CVNA', 'BARK', 'GM', 'BLNK', 'QS', 'F', 'RIVN', 'FCEL', 'CHPT', 'LCID', 
    'UPST', 'PYPL', 'AFRM', 'V', 'MA', 'AXP', 'BITO', 'COIN', 'RIOT', 'MARA', 'MSTR', 'SI', 
    'DKNG', 'PENN', 'BETZ', 'REGN', 'VRTX', 'MRK', 'UNH', 'TMO', 'ISRG', 'ABT', 'IDXX', 'TDOC', 'CRSP', 
    'BRK.B', 'ETN', 'CAT', 'BLD', 'U', 'RBLX', 'SKLZ', 'FSLY', 'TRIP', 'EXPE', 'BKNG', 'ABNB', 'DIS', 'WMT', 
    'COST', 'TGT', 'LOW', 'HD', 'DT', 'SNPS', 'CDNS', 'MDB', 'ORCL', 'NOW', 'ADP', 'SNOW', 'ANSS', 'DDOG', 
    'FROG', 'ADSK', 'INTU', 'TEAM', 'WDAY', 'CRM', 'PAYC', 'ANET', 'ADBE', 'ACN', 'EPAM', 'ZM', 'TTD', 'TWLO', 
    'DASH', 'APPS', 'DOCU', 'AI', 'AKAM', 'QLYS', 'PANW', 'FTNT', 'CRWD', 'TENB', 'OKTA', 'ZS', 
    'NET', 'S', 'UMC', 'ASML', 'KEYS', 'CRUS', 'AMD', 'AVGO', 'MU', 'KLAC', 'TXN', 'QRVO', 'TSM', 'SWKS', 'AMBA', 
    'STM', 'MCHP', 'ON', 'QCOM', 'SOXX', 'MRVL', 'ADI', 'LRCX', 'AMAT', 'WDC', 'NXPI', 'TER', 'MPWR', 'INTC', 
    'GFS', 'STX', 'A', 'ZBRA', 'ENTG', 'ONTO', 'TRMB', 'BNTX', 'PFE', 'MRNA', 'NVAX', 'FCX', 'CF', 'DRI', 
    'PEP', 'XOM', 'LLY', 'CL', 'MCD', 'KO', 'GE', 'CVX', 'FISV', 'DE', 'WM', 'HLT', 'FUTU', 'UBER', 
    'TIGR', 'EQIX', 'DPZ', 'CSCO', 'COKE', 'SONY', 'FDS', 'MCO', 'GRAB', 'PTON', 'AMT', 'LIT', 'CMG', 'IPO', 
    'PSTG', 'INMD', 'NNDM', 'MP', 'FUBO', 'SPOT', 'ALGN', 'PZZA', 'LOVE', 'LMND', 'POOL', 'PLTR', 'ROKU', 
    'CELH', 'NFLX', 'DHI', 'DELL', 'GOOG'
]
# Ensure uniqueness
KNOWN_STOCKS = list(set(KNOWN_STOCKS))

LIME_STOCKS = [
    'USO', 'XOP', 'BUG', 'CLOU', 'IGV', 'HACK', 'CIBR', 'TAN', 'IHI', 'IPAY', 
    'VTV', 'KBE', 'KRE', 'VUG', 'PBW', 'MAGS', 'XRT', 'JETS', 'XTL', 'SHLD', 
    'IBIT', 'UFO', 'XBI', 'SLX', 'ITA', 'REMX', 'LIT', 'KWEB', 'XHB', 'SMH', 
    'BLOK', 'XME', 'URA', 'DRAM', 'GDX', 'WGMI', 'COPX', 'SIL', 'IAT', 'ITB'
]

# 3. Sidebar Inputs
with st.sidebar:
    st.header("Settings")
    benchmark = st.selectbox("Benchmark", ["^GSPC", "^IXIC"], index=0)
    rs_length = st.number_input("RS Lookback Length", value=90, min_value=10)
    top_n = st.number_input("Top N for Group Avg", value=5, min_value=1)
    show_all_rs = st.toggle("Show RS < 80 Tickers", value=False)
    
    if st.button("Clear Cache & Refresh"):
        st.cache_data.clear()

# 4. IMPLEMENTATION OF NEW NORMALIZED RS METHOD AND EMA CLOUD
@st.cache_data(ttl=3600)
def get_rs_and_cloud_data_cached(tickers_tuple, benchmark_ticker, length): # <-- Added length parameter
    tickers = list(tickers_tuple)
    try:
        all_tickers = tickers + [benchmark_ticker]
        # Download data (ensuring enough historical data to compute the rolling min/max lookback window)
        data = yf.download(all_tickers, period="2y", interval="1d", progress=False)
        
        close_data = data['Close']
        high_data = data['High']
        low_data = data['Low']
        
        valid_tickers = [t for t in tickers if t in close_data.columns and close_data[t].notna().sum() >= length]
        if not valid_tickers: return None, None, None, {}, None, None

        # --- New RS Logic ---
        bench_close = close_data[benchmark_ticker]
        stock_scores = {}
        stock_scores_prev = {}
        stock_scores_1m = {}
        cloud_tickers = []
        price_lookup = {}  # Added to track individual stock prices out of cache cleanly

        for ticker in valid_tickers:
            # 1. rsClose = close / indexClose
            rs_ratio_series = close_data[ticker] / bench_close
            
            # 2. hh = ta.highest(rsClose, length) | ll = ta.lowest(rsClose, length)
            # Use rolling window to get historical highs and lows of the ratio
            hh = rs_ratio_series.rolling(window=length).max()
            ll = rs_ratio_series.rolling(window=length).min()
            
            # Get the absolute most recent values (today's values)
            current_rs = rs_ratio_series.iloc[-1]
            current_hh = hh.iloc[-1]
            current_ll = ll.iloc[-1]

            # Get values from 1 week ago (5 trading days ago)
            prev_rs = rs_ratio_series.iloc[-6]
            prev_hh = hh.iloc[-6]
            prev_ll = ll.iloc[-6]

            # Get values from 1 month ago (21 trading days ago)
            m1_rs = rs_ratio_series.iloc[-22]
            m1_hh = hh.iloc[-22]
            m1_ll = ll.iloc[-22]
            
            # 3. Normalized logic: ((99 - 1) * (rsClose - ll) / (hh - ll)) + 1
            if pd.isna(current_hh) or pd.isna(current_ll) or current_hh == current_ll:
                total_score = 0
            else:
                # Convert the entire formula directly into an integer
                total_score = int(((99 - 1) * (current_rs - current_ll) / (current_hh - current_ll)) + 1)
            
            if pd.isna(prev_hh) or pd.isna(prev_ll) or prev_hh == prev_ll:
                total_score_prev = 0
            else:
                total_score_prev = int(((99 - 1) * (prev_rs - prev_ll) / (prev_hh - prev_ll)) + 1)

            if pd.isna(m1_hh) or pd.isna(m1_ll) or m1_hh == m1_ll:
                total_score_1m = 0
            else:
                total_score_1m = int(((99 - 1) * (m1_rs - m1_ll) / (m1_hh - m1_ll)) + 1)

            # This will now store a clean whole number (e.g., 85 instead of 85.34)
            stock_scores[ticker] = total_score
            stock_scores_prev[ticker] = total_score_prev
            stock_scores_1m[ticker] = total_score_1m

            # EMA Cloud Calculation (21 EMA of High/Low) - Kept Unchanged
            ema_low = low_data[ticker].ewm(span=21, adjust=False).mean().iloc[-1]
            ema_high = high_data[ticker].ewm(span=21, adjust=False).mean().iloc[-1]
            current_price = close_data[ticker].iloc[-1]
            price_lookup[ticker] = current_price  # Cache current price reference maps
            
            if ema_low <= current_price <= ema_high:
                cloud_tickers.append(ticker)

        # Convert dictionary metrics to Pandas Series
        rs_perf_raw = pd.Series(stock_scores).astype(int)
        rs_perf_prev_raw = pd.Series(stock_scores_prev).astype(int)
        rs_perf_1m_raw = pd.Series(stock_scores_1m).astype(int)
        
        # Build a list of tickers that strictly have a price greater than 20
        valid_price_tickers = [ticker for ticker, price in price_lookup.items() if price > 20]
        
        # Filter the series so only stocks with a price > 20 remain
        rs_perf = rs_perf_raw[rs_perf_raw.index.isin(valid_price_tickers)]
        rs_perf_prev = rs_perf_prev_raw[rs_perf_prev_raw.index.isin(valid_price_tickers)]
        rs_perf_1m = rs_perf_1m_raw[rs_perf_1m_raw.index.isin(valid_price_tickers)]
        
        return rs_perf, rs_perf, cloud_tickers, price_lookup, rs_perf_prev, rs_perf_1m
    except Exception as e:
        st.error(f"Error: {e}")
        return None, None, None, {}, None, None

# Reference Scanner Logic Functions
def scan_two_botak(df, lookback=0):
    idx = -1 - lookback
    if len(df) < abs(idx) + 1: return False
    botak = (
        (abs(df['Close'] - df['High']) < 0.05) & 
        (df['Close'] > df['Open'])
    )
    percentile = (
        (df['Close'] > df['Open']) & 
        (((df['Close'] - df['Open']) / ((df['High'] - df['Open']).replace(0, 0.001))) > 0.9)
    )
    twoBotak = (
        ((botak & botak.shift(1)) |
        (botak & percentile.shift(1)) |
        (percentile & botak.shift(1)) |
        (percentile & percentile.shift(1))) &
        (df['Close'] > 20)
    )
    return bool(twoBotak.iloc[idx])

def scan_engulfing(df, lookback=0):
    idx = -1 - lookback
    if len(df) < 30 + lookback: return False, False
    bullish_engulfing = (
        (df['Open'] < df['Low'].shift(1)) &
        (df['Close'] > df['High'].shift(1))
    )
    engulf_count_series = bullish_engulfing.rolling(window=30).sum()
    
    # Logic for historical comparison
    df_temp = df.iloc[:len(df)-lookback] if lookback > 0 else df
    current_idx = df_temp.index[-1]
    
    engulf_closes = df_temp.loc[bullish_engulfing, 'Close']
    prior_engulfs = engulf_closes[engulf_closes.index < current_idx]

    eng1 = prior_engulfs.iloc[-1] if len(prior_engulfs) >= 1 else 0
    eng2 = prior_engulfs.iloc[-2] if len(prior_engulfs) >= 2 else 0
    eng3 = prior_engulfs.iloc[-3] if len(prior_engulfs) >= 3 else 0

    current_close = df_temp['Close'].iloc[-1]
    current_count = engulf_count_series.iloc[idx]

    two_engulf = (
        (current_count >= 2) and
        (current_close > 20) and
        (current_close > eng1) and
        (current_close > eng2)
    )
    three_engulf = (
        (current_count >= 3) and
        (current_close > 20) and
        (current_close > eng1) and
        (current_close > eng2) and
        (current_close > eng3)
    )
    return bool(two_engulf), bool(three_engulf)

def scan_powertrend(df, lookback=0):
    idx = -1 - lookback
    if len(df) < 52 + lookback: return False
    powerma = df['Close'].ewm(span=50, adjust=False).mean()
    gradient = powerma - powerma.shift(1)
    gradientPct = ((powerma - powerma.shift(1)) / powerma.shift(1)) * 100
    absGradient = abs(gradientPct)
    powertrend = (
        (gradient > 0) &
        (absGradient >= 1.0) & 
        (df['Close'] >= 20)
    )
    return bool(powertrend.iloc[idx])

def scan_powertrend_not_extended(df, lookback=0):
    idx = -1 - lookback
    if len(df) < 52 + lookback: return False
    powerma = df['Close'].ewm(span=50, adjust=False).mean()
    gradient = powerma - powerma.shift(1)
    gradientPct = ((powerma - powerma.shift(1)) / powerma.shift(1)) * 100
    absGradient = abs(gradientPct)
    
    powertrend = (
        (gradient > 0) &
        (absGradient >= 1.0) &
        (df['Close'] >= 20)
    )

    high_low = df['High'] - df['Low']
    high_close = abs(df['High'] - df['Close'].shift(1))
    low_close = abs(df['Low'] - df['Close'].shift(1))
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    absATR = tr.rolling(14).mean()
    atrPercent = (absATR / df['Close']) * 100
    sma50 = df['Close'].rolling(50).mean()
    percentGainFromMA = ((df['Close'] - sma50) / sma50) * 100
    atrMultiple2 = percentGainFromMA / atrPercent.replace(0, 0.001)
    atrMultiple = (atrMultiple2 * 10).fillna(0).astype(int) / 10

    result = (powertrend & (atrMultiple <= 4))
    return bool(result.iloc[idx])

def scan_value_trap(df, lookback=0):
    idx = -1 - lookback
    if len(df) < 50 + lookback: return False
    
    high_low = df['High'] - df['Low']
    high_close = abs(df['High'] - df['Close'].shift(1))
    low_close = abs(df['Low'] - df['Close'].shift(1))
    
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    absATR = tr.rolling(14).mean()
    atrPercent = (absATR / df['Close']) * 100
    
    sma50 = df['Close'].rolling(50).mean()
    percentGainFromMA = ((df['Close'] - sma50) / sma50) * 100
    
    atrMultiple2 = percentGainFromMA / atrPercent.replace(0, 0.001)
    atrMultiple2 = atrMultiple2.replace([float('inf'), -float('inf')], pd.NA)
    atrMultiple = ((atrMultiple2.fillna(0) * 10).astype(int) / 10)
    
    result = ((atrMultiple < -4) & (df['Close'] >= 20))
    return bool(result.iloc[idx])

def scan_ppp(df, lookback=0):
    idx = -1 - lookback
    if len(df) < 200 + lookback: return False
    high_low = df['High'] - df['Low']
    high_close = abs(df['High'] - df['Close'].shift(1))
    low_close = abs(df['Low'] - df['Close'].shift(1))
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    myAtr = tr.rolling(14).mean()
    myAtr3 = myAtr / df['Close'] * 100
    dynamicSensitivity = myAtr3 * 0.2

    day0 = (df['Open'] + df['Close']) / 2
    day1 = day0.shift(1)
    day2 = day0.shift(2)

    diff0 = abs((day0 - day1) / day1.replace(0, 0.001) * 100)
    diff1 = abs((day1 - day2) / day2.replace(0, 0.001) * 100)

    sma50 = df['Close'].rolling(50).mean()
    sma200 = df['Close'].rolling(200).mean()

    ma21_and_ma50_or_ma200 = (
        (
            ((df['Close'] >= sma200) & (df['Close'] >= sma50))
        ) &
        (df['Close'] >= 20)
    )

    ppp = (
        (diff0 < dynamicSensitivity) &
        (diff1 < dynamicSensitivity) &
        ma21_and_ma50_or_ma200
    )
    return bool(ppp.iloc[idx])

@st.cache_data(ttl=3600)
def process_pattern_scanners(stocks_list):
    try:
        raw_data = yf.download(stocks_list, period="2y", interval="1d", progress=False)
        
        # Today's Matches
        botak_matches = []
        engulf2_matches = []
        engulf3_matches = []
        powertrend_matches = []
        powertrend_ne_matches = []
        value_trap_matches = []
        ppp_matches = []
        
        # Yesterday's Matches (for color logic)
        botak_yest = []
        engulf2_yest = []
        engulf3_yest = []
        powertrend_yest = []
        powertrend_ne_yest = []
        value_trap_yest = []
        ppp_yest = []

        # Initialize internal metrics tracking variables
        # --- Inside process_pattern_scanners loop setup ---
        know_total_count = 0
        know_positive_count = 0
        email_content_stocks = []  # Now tracks tuples of (ticker, is_new_addition)
        email_content_removed = [] # Tracks dropped Minervini stocks compared to yesterday
        extra_52wk_high_symbols = []
        extra_52wk_high_removed = []
        ema200_above_count = 0
        ema200_total_count = 0

        for ticker in stocks_list:
            try:
                if len(stocks_list) > 1:
                    ticker_df = pd.DataFrame({
                        'Open': raw_data['Open'][ticker],
                        'High': raw_data['High'][ticker],
                        'Low': raw_data['Low'][ticker],
                        'Close': raw_data['Close'][ticker],
                        'Volume': raw_data['Volume'][ticker]
                    }).dropna()
                else:
                    ticker_df = raw_data.dropna().copy()
                
                if ticker_df.empty or len(ticker_df) < 50:
                    continue

                # Calculate EMA 200 for the current stock
                if len(ticker_df) >= 200:
                    current_close = ticker_df['Close'].iloc[-1]
                    ema200 = ticker_df['Close'].ewm(span=200, adjust=False).mean().iloc[-1]
                    ema200_total_count += 1
                    if current_close > ema200:
                        ema200_above_count += 1
                
                # --- ADJUSTED FOR NEW ADDITIONS TODAY VS YESTERDAY ---
                if ticker in KNOWN_STOCKS and len(ticker_df) >= 261:
                    # Setup SMA structures
                    ticker_df["SMA_50"] = round(ticker_df['Close'].rolling(window=50).mean(), 2)
                    ticker_df["SMA_150"] = round(ticker_df['Close'].rolling(window=150).mean(), 2)
                    ticker_df["SMA_200"] = round(ticker_df['Close'].rolling(window=200).mean(), 2)

                    # --- EVALUATE TODAY (Index -1) ---
                    currentClose = ticker_df["Close"].iloc[-1]
                    prevClose = ticker_df["Close"].iloc[-2]
                    Volume = ticker_df["Volume"].iloc[-1]
                    moving_average_50 = ticker_df["SMA_50"].iloc[-1]
                    moving_average_200 = ticker_df["SMA_200"].iloc[-1]
                    moving_average_200_20 = ticker_df["SMA_200"].iloc[-20] if len(ticker_df) >= 20 else 0
                    
                    low_of_52week = round(min(ticker_df["Low"].iloc[-260:]), 2)
                    high_of_52week = round(ticker_df["High"].iloc[-260:-1].max(), 2)

                    cond1_t = int(currentClose > moving_average_50 > moving_average_200)
                    cond2_t = int(moving_average_50 > moving_average_200)
                    cond3_t = int(moving_average_200 > moving_average_200_20)
                    cond4_t = int(moving_average_50 > moving_average_200)
                    cond5_t = int(currentClose > moving_average_50)
                    cond6_t = int(currentClose >= (1.3 * low_of_52week))
                    cond7_t = int(currentClose >= (0.75 * high_of_52week))
                    cond8_t = int(currentClose >= 20)
                    cond9_t = int(Volume > 20000)
                    cond10_t = int((Volume * currentClose) > 2000000)
                    
                    total_today = (cond1_t + cond2_t + cond3_t + cond4_t + cond5_t + 
                                   cond6_t + cond7_t + cond8_t + cond9_t + cond10_t)

                    # --- EVALUATE YESTERDAY (Index -2) ---
                    yestClose = ticker_df["Close"].iloc[-2]
                    yestVolume = ticker_df["Volume"].iloc[-2]
                    yest_ma_50 = ticker_df["SMA_50"].iloc[-2]
                    yest_ma_200 = ticker_df["SMA_200"].iloc[-2]
                    yest_ma_200_20 = ticker_df["SMA_200"].iloc[-21] if len(ticker_df) >= 21 else 0
                    
                    yest_low_of_52week = round(min(ticker_df["Low"].iloc[-261:-1]), 2)
                    yest_high_of_52week = round(ticker_df["High"].iloc[-261:-2].max(), 2)

                    cond1_y = int(yestClose > yest_ma_50 > yest_ma_200)
                    cond2_y = int(yest_ma_50 > yest_ma_200)
                    cond3_y = int(yest_ma_200 > yest_ma_200_20)
                    cond4_y = int(yest_ma_50 > yest_ma_200)
                    cond5_y = int(yestClose > yest_ma_50)
                    cond6_y = int(yestClose >= (1.3 * yest_low_of_52week))
                    cond7_y = int(yestClose >= (0.75 * yest_high_of_52week))
                    cond8_y = int(yestClose >= 20)
                    cond9_y = int(yestVolume > 20000)
                    cond10_y = int((yestVolume * yestClose) > 2000000)

                    total_yesterday = (cond1_y + cond2_y + cond3_y + cond4_y + cond5_y + 
                                       cond6_y + cond7_y + cond8_y + cond9_y + cond10_y)
                    
                    is_at_52wk_high_today = currentClose >= high_of_52week
                    is_at_52wk_high_yest = yestClose >= yest_high_of_52week
                    
                    qualified_today_52w = (is_at_52wk_high_today and total_today < 10)
                    was_qualified_yest = (is_at_52wk_high_yest and total_yesterday < 10)
                    
                    if qualified_today_52w:
                        is_new_addition_52w = not was_qualified_yest
                        extra_52wk_high_symbols.append((ticker, is_new_addition_52w))
                    elif was_qualified_yest:
                        extra_52wk_high_removed.append(ticker)

                    # --- SET CONTROLLER FLAGS ---
                    if total_today >= 10:
                        know_total_count += 1
                        is_new_addition = (total_yesterday < 10)
                        is_positive_today = (currentClose > prevClose)
                        email_content_stocks.append((ticker, is_new_addition, is_positive_today))
                        
                        if currentClose > prevClose:
                            know_positive_count += 1
                    elif total_yesterday >= 10:
                        email_content_removed.append(ticker)

                # Scan Today
                if scan_two_botak(ticker_df, 0): botak_matches.append(ticker)
                e2, e3 = scan_engulfing(ticker_df, 0)
                if e2: engulf2_matches.append(ticker)
                if e3: engulf3_matches.append(ticker)
                if scan_powertrend(ticker_df, 0): powertrend_matches.append(ticker)
                if scan_powertrend_not_extended(ticker_df, 0): powertrend_ne_matches.append(ticker)
                if scan_value_trap(ticker_df, 0): value_trap_matches.append(ticker)
                if scan_ppp(ticker_df, 0): ppp_matches.append(ticker)

                # Scan Yesterday
                if scan_two_botak(ticker_df, 1): botak_yest.append(ticker)
                e2y, e3y = scan_engulfing(ticker_df, 1)
                if e2y: engulf2_yest.append(ticker)
                if e3y: engulf3_yest.append(ticker)
                if scan_powertrend(ticker_df, 1): powertrend_yest.append(ticker)
                if scan_powertrend_not_extended(ticker_df, 1): powertrend_ne_yest.append(ticker)
                if scan_value_trap(ticker_df, 1): value_trap_yest.append(ticker)
                if scan_ppp(ticker_df, 1): ppp_yest.append(ticker)

            except:
                continue
                
        botak_matches.sort()
        engulf2_matches.sort()
        engulf3_matches.sort()
        powertrend_matches.sort()
        powertrend_ne_matches.sort()
        value_trap_matches.sort()
        ppp_matches.sort()
        
        know_pos_pct = (know_positive_count / know_total_count * 100) if know_total_count > 0 else 0
        pct_above_ema200 = (ema200_above_count / ema200_total_count * 100) if ema200_total_count > 0 else 0
        
        return (botak_matches, engulf2_matches, engulf3_matches, powertrend_matches, powertrend_ne_matches, value_trap_matches, ppp_matches,
                botak_yest, engulf2_yest, engulf3_yest, powertrend_yest, powertrend_ne_yest, value_trap_yest, ppp_yest, 
                know_pos_pct, know_positive_count, know_total_count, email_content_stocks, email_content_removed,
                extra_52wk_high_symbols, extra_52wk_high_removed, pct_above_ema200)
    except:
        return [], [], [], [], [], [], [], [], [], [], [], [], [], [], 0, 0, 0, [], [], [], [], 0

# 5. UI Layout & Logic
#st.markdown("<h3 style='font-size: 16px; margin-bottom: 10px;'>📊 Relative Strength Screener</h3>", unsafe_allow_html=True)

all_data = []
progress_bar = st.progress(0)
status_text = st.empty()

industry_items = list(INDUSTRIES.items())
for idx, (industry_name, tickers) in enumerate(industry_items):
    status_text.text(f"Processing {industry_name}...")
    perf, rs_scores, cloud_list, price_lookup, rs_scores_prev, rs_scores_1m = get_rs_and_cloud_data_cached(tuple(tickers), benchmark, 90)
    
    if rs_scores is not None:
        top_n_scores = rs_scores.nlargest(int(top_n))
        group_avg = top_n_scores.mean()
        # Calculate past group average safely matching dynamic length checks
        if rs_scores_prev is not None and not rs_scores_prev.empty:
            top_n_scores_prev = rs_scores_prev.nlargest(int(top_n))
            group_avg_prev = top_n_scores_prev.mean()
        else:
            group_avg_prev = group_avg

        if rs_scores_1m is not None and not rs_scores_1m.empty:
            top_n_scores_1m = rs_scores_1m.nlargest(int(top_n))
            group_avg_1m = top_n_scores_1m.mean()
        else:
            group_avg_1m = group_avg

        df_tickers = pd.DataFrame({"Ticker": rs_scores.index, "RS Score": rs_scores.values}).sort_values(by="RS Score", ascending=False)
        all_data.append({
            "Industry": industry_name, 
            "Group RS": group_avg, 
            "Group RS Prev": group_avg_prev, 
            "Group RS 1M": group_avg_1m, 
            "Tickers": df_tickers, 
            "Cloud": cloud_list,
            "Prices": price_lookup  # Store prices securely into dataset
        })
    
    progress_bar.progress((idx + 1) / len(industry_items))

status_text.empty()
progress_bar.empty()

# 6. Compact Display Logic
if all_data:
    df_main = pd.DataFrame([{"Industry": item["Industry"], "Group RS": item["Group RS"], "Group RS Prev": item["Group RS Prev"], "Group RS 1M": item["Group RS 1M"]} for item in all_data])

    col1, col2 = st.columns([1, 1])
    with col1:
        sort_by = st.selectbox("Sort by", ["Group RS (High to Low)", "Industry (A-Z)", "Group RS (Low to High)"])
    with col2:
        sort_order = st.radio("Order", ["Descending", "Ascending"], horizontal=True)

    if "Industry" in sort_by:
        df_main = df_main.sort_values("Industry", ascending=(sort_order == "Ascending"))
    else:
        df_main = df_main.sort_values("Group RS", ascending=(sort_order == "Ascending"))

    # Determine structural context ranking profiles before generation iteration sequences
    df_main['Current Rank'] = range(1, len(df_main) + 1)
    
    # Sort by previous scores to resolve previous visual ranks
    df_prev_sorted = df_main.sort_values("Group RS Prev", ascending=(sort_order == "Ascending")).copy()
    df_prev_sorted['Prev Rank'] = range(1, len(df_prev_sorted) + 1)
    
    # Sort by 1M scores to resolve 1 month visual ranks
    df_1m_sorted = df_main.sort_values("Group RS 1M", ascending=(sort_order == "Ascending")).copy()
    df_1m_sorted['1M Rank'] = range(1, len(df_1m_sorted) + 1)

    # Map elements back directly inside the pipeline
    rank_map = dict(zip(df_prev_sorted['Industry'], df_prev_sorted['Prev Rank']))
    df_main['Prev Rank'] = df_main['Industry'].map(rank_map)

    rank_map_1m = dict(zip(df_1m_sorted['Industry'], df_1m_sorted['1M Rank']))
    df_main['1M Rank'] = df_main['Industry'].map(rank_map_1m)

    st.markdown("""
    <style>
    .ticker-badge { 
        display: inline-block; 
        margin: 1px 3px; 
        padding: 1px 5px; 
        border: 1px solid #444; 
        border-radius: 3px; 
        font-size: 11px; 
        background-color: #1e1e1e; 
        color: #eee; 
        white-space: nowrap;
    }
    .cloud-badge {
        background-color: #2e4a3e;
        border: 1px solid #4ecdc4;
    }
    .pattern-badge {
        background-color: #1f3a52;
        border: 1px solid #3a86c8;
        color: #fff;
        font-weight: bold;
    }
    .new-pattern-badge {
        background-color: #FFD700;
        border: 1px solid #B8860B;
        color: #000;
        font-weight: bold;
    }
    .removed-badge {
        background-color: #2d2d2d;
        border: 1px solid #555555;
        color: #888888;
        text-decoration: line-through;
    }
    .lime-badge {
        background-color: #00FF00;
        border: 1px solid #009900;
        color: #000000;
        font-weight: bold;
    }
    .ticker-name { font-weight: bold; color: #ffffff; margin-right: 4px; }
    .ticker-rs { color: #4ecdc4; font-weight: normal; }
    table { width:100%; border-collapse: collapse; }
    th { padding: 4px 8px !important; background-color: #1f77b4; color: white; font-size: 12px; }
    td { padding: 2px 8px !important; border-bottom: 1px solid #333; font-size: 12px; }
    </style>
    """, unsafe_allow_html=True)

    table_html = """<table>
    <thead><tr>
    <th style="text-align: center; width: 30px;">#</th>
    <th style="text-align: left;">Industry</th>
    <th style="text-align: center; width: 40px;">RS</th>
    <th style="text-align: center; width: 40px;">1W</th>
    <th style="text-align: center; width: 40px;">1M</th>
    <th style="text-align: left;">Tickers</th>
    <th style="text-align: left; width: 300px;">21ema Cloud</th>
    </tr></thead><tbody>"""

    for row_num, (i, row) in enumerate(df_main.iterrows(), start=1):
        item = next(d for d in all_data if d["Industry"] == row["Industry"])
        rs_lookup = dict(zip(item["Tickers"]["Ticker"], item["Tickers"]["RS Score"]))

        # Calculate Rank Shift strings cleanly dynamically
        cur_r = row['Current Rank']
        prv_r = row['Prev Rank']
        shift = prv_r - cur_r
        if shift > 0:
            rank_str = f'<span style="color: #00FF00; font-weight: bold;">+{shift}</span>'
        elif shift < 0:
            rank_str = f'<span style="color: #FF7F7F; font-weight: bold;">{shift}</span>'
        else:
            rank_str = f'<span style="color: #aaaaaa;">0</span>'
        
        # Calculate 1M Rank Shift strings cleanly dynamically
        prv_r_1m = row['1M Rank']
        shift_1m = prv_r_1m - cur_r
        if shift_1m > 0:
            rank_str_1m = f'<span style="color: #00FF00; font-weight: bold;">+{shift_1m}</span>'
        elif shift_1m < 0:
            rank_str_1m = f'<span style="color: #FF7F7F; font-weight: bold;">{shift_1m}</span>'
        else:
            rank_str_1m = f'<span style="color: #aaaaaa;">0</span>'

        ticker_html = ""
        for _, r in item["Tickers"].iterrows():
            ticker_sym = r["Ticker"]
            rs_score = r["RS Score"]
            ticker_price = item["Prices"].get(ticker_sym, 0)
            
            if (show_all_rs or rs_score >= 80) and ticker_price > 20:
                # If the ticker is inside KNOWN_STOCKS, apply high-contrast dark text rules
                if ticker_sym in LIME_STOCKS:
                    ticker_html += (
                        f'<div class="ticker-badge lime-badge">'
                        f'<span class="ticker-name" style="color: #000000; font-weight: bold;">{ticker_sym}</span>' 
                        f'<span class="ticker-rs" style="color: #000000; font-weight: bold; margin-left: 5px;">{rs_score:.0f}</span>' 
                        f'</div>'
                    )
                elif ticker_sym in KNOWN_STOCKS:
                    ticker_html += (
                        f'<div class="ticker-badge new-pattern-badge">'
                        f'<span class="ticker-name" style="color: #111111; font-weight: bold;">{ticker_sym}</span>' # Clean high-contrast dark charcoal text
                        f'<span class="ticker-rs" style="color: #004d26; font-weight: bold;">{r["RS Score"]:.0f}</span>' # Highly legible dark gold numbers
                        f'</div>'
                    )
                else:
                    # Standard matching dark badge layout for everything else
                    ticker_html += (
                        f'<div class="ticker-badge">'
                        f'<span class="ticker-name">{ticker_sym}</span>'
                        f'<span class="ticker-rs">{r["RS Score"]:.0f}</span>'
                        f'</div>'
                    )
        
        #cloud_html = "".join([f'<div class="ticker-badge cloud-badge">{c}</div>' for c in item["Cloud"]])
        cloud_html = ""
        sorted_cloud = sorted(item["Cloud"], key=lambda sym: rs_lookup.get(sym, 0), reverse=True)

        # --- SLICE LOGIC: Slices the sorted array to isolate the top 5 items only ---
        top_5_cloud = sorted_cloud[:5]
        
        for cloud_sym in top_5_cloud:
            # Retrieve the RS Score from our data map (default to 0 if not found)
            cloud_rs = rs_lookup.get(cloud_sym, 0)
            
            if cloud_sym in LIME_STOCKS:
                cloud_html += (
                    f'<div class="ticker-badge lime-badge">'
                    f'<span class="ticker-name" style="color: #000000; font-weight: bold;">{cloud_sym}</span>'
                    f'<span class="ticker-rs" style="color: #000000; font-weight: bold; margin-left: 5px;">{cloud_rs:.0f}</span>'
                    f'</div>'
                )
            elif cloud_sym in KNOWN_STOCKS:
                cloud_html += (
                    f'<div class="ticker-badge new-pattern-badge">'
                    f'<span class="ticker-name" style="color: #111111; font-weight: bold;">{cloud_sym}</span>'
                    f'<span class="ticker-rs" style="color: #004d26; font-weight: bold;">{cloud_rs:.0f}</span>'
                    f'</div>'
                )
            else:
                cloud_html += (
                    f'<div class="ticker-badge">'
                    f'<span class="ticker-name">{cloud_sym}</span>'
                    f'<span class="ticker-rs">{cloud_rs:.0f}</span>'
                    f'</div>'
                )
        bg_color = "#262730" if row_num % 2 == 0 else "#0e1117"
        
        table_html += f"""<tr style="background-color: {bg_color};">
        <td style="text-align: center; color: #888; font-weight: bold;">{row_num}</td>
        <td style="font-weight: bold; color: #ffffff;">{row['Industry']}</td>
        <td style="text-align: center; color: #4ecdc4; font-weight: bold;">{row['Group RS']:.1f}</td>
        <td style="text-align: center; vertical-align: middle;">{rank_str}</td>
        <td style="text-align: center; vertical-align: middle;">{rank_str_1m}</td>
        <td>{ticker_html}</td>
        <td>{cloud_html}</td></tr>"""

    table_html += "</tbody></table>"
    st.markdown(table_html, unsafe_allow_html=True)

# 7. EXTRA SEPARATE PATTERNS SCANNING BLOCK
#st.markdown("---")
#st.markdown("### 🔍 Technical Pattern Screener (KNOWN_STOCKS Database)")

@st.cache_data(ttl=3600)
def compute_two_botak_history(stocks_list):
    try:
        chart_raw_data = yf.download(list(stocks_list), period="2y", interval="1d", progress=False)

        ticker_dfs = {}
        for ticker in stocks_list:
            if len(stocks_list) > 1:
                t_df = pd.DataFrame({
                    'Open': chart_raw_data['Open'][ticker],
                    'High': chart_raw_data['High'][ticker],
                    'Low': chart_raw_data['Low'][ticker],
                    'Close': chart_raw_data['Close'][ticker],
                    'Volume': chart_raw_data['Volume'][ticker]
                }).dropna()
            else:
                t_df = chart_raw_data.dropna().copy()

            if not t_df.empty:
                ticker_dfs[ticker] = t_df

        if not ticker_dfs:
            return pd.DataFrame()

        any_ticker = list(ticker_dfs.keys())[0]
        full_timeline = ticker_dfs[any_ticker].index

        days_to_compute = min(60, len(full_timeline))
        records = []

        for i in range(days_to_compute - 1, -1, -1):
            idx = -1 - i
            current_date = full_timeline[idx]

            day_total_count = 0

            for ticker, df in ticker_dfs.items():
                if len(df) < 2:
                    continue

                # =========================
                # FULL SERIES LOGIC (FIXED)
                # =========================
                df_full = df

                botak = (
                    (abs(df_full['Close'] - df_full['High']) < 0.05) &
                    (df_full['Close'] > df_full['Open'])
                )

                percentile = (
                    (df_full['Close'] > df_full['Open']) &
                    (((df_full['Close'] - df_full['Open']) /
                      ((df_full['High'] - df_full['Open']).replace(0, 0.001))) > 0.9)
                )

                two_botak_series = (
                    ((botak & botak.shift(1)) |
                     (botak & percentile.shift(1)) |
                     (percentile & botak.shift(1)) |
                     (percentile & percentile.shift(1))) &
                    (df_full['Close'] > 20)
                )

                # =========================
                # SAFE HISTORICAL PROJECTION
                # =========================
                if len(two_botak_series) > abs(idx):
                    if bool(two_botak_series.iloc[idx]):
                        day_total_count += 1

            records.append({
                "Date": current_date.strftime("%Y-%m-%d"),
                "Two Botak Count": day_total_count
            })

        return pd.DataFrame(records)

    except Exception as e:
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def compute_engulfing_history(stocks_list):
    try:
        raw_data = yf.download(list(stocks_list), period="2y", interval="1d", progress=False)

        ticker_dfs = {}
        for ticker in stocks_list:
            if len(stocks_list) > 1:
                df = pd.DataFrame({
                    'Open': raw_data['Open'][ticker],
                    'High': raw_data['High'][ticker],
                    'Low': raw_data['Low'][ticker],
                    'Close': raw_data['Close'][ticker],
                    'Volume': raw_data['Volume'][ticker]
                }).dropna()
            else:
                df = raw_data.dropna().copy()

            if not df.empty:
                ticker_dfs[ticker] = df

        if not ticker_dfs:
            return pd.DataFrame()

        timeline = ticker_dfs[list(ticker_dfs.keys())[0]].index
        days = min(60, len(timeline))

        records = []

        for i in range(days - 1, -1, -1):
            idx = -1 - i
            date = timeline[idx]

            count_2x = 0
            count_3x = 0

            for ticker, df in ticker_dfs.items():
                if len(df) < 30:
                    continue

                df_full = df

                bullish_engulfing = (
                    (df_full['Open'] < df_full['Low'].shift(1)) &
                    (df_full['Close'] > df_full['High'].shift(1))
                )

                engulf_count_series = bullish_engulfing.rolling(window=30).sum()

                # ---- SAFE historical alignment ----
                if len(engulf_count_series) <= abs(idx):
                    continue

                current_close = df_full['Close'].iloc[idx]
                current_count = engulf_count_series.iloc[idx]

                if current_count >= 2 and current_close > 20:
                    count_2x += 1

                if current_count >= 3 and current_close > 20:
                    count_3x += 1

            records.append({
                "Date": date.strftime("%Y-%m-%d"),
                "2x Engulfing Count": count_2x,
                "3x Engulfing Count": count_3x
            })

        return pd.DataFrame(records)

    except Exception:
        return pd.DataFrame()

with st.spinner("Scanning pattern anomalies across known instruments..."):
    results = process_pattern_scanners(tuple(KNOWN_STOCKS))
    two_botak_hist = compute_two_botak_history(tuple(KNOWN_STOCKS))
    engulf_hist = compute_engulfing_history(tuple(KNOWN_STOCKS))
    b_list, e2_list, e3_list, pt_list, ptne_list, vt_list, ppp_list = results[:7]
    b_yest, e2_yest, e3_yest, pt_yest, ptne_yest, vt_yest, ppp_yest = results[7:14]
    know_pos_pct, know_positive_count, know_total_count, email_content_stocks, email_content_removed, extra_52wk_high_symbols, extra_52wk_high_removed, pct_above_ema200 = results[14:]

st.markdown("---")

# ==============================================================================
# 8. HISTORICAL KNOW_TOTAL_COUNT 30-DAY CHART (Completely New Logic at Bottom)
# ==============================================================================
@st.cache_data(ttl=3600)
def compute_historical_know_counts(stocks_list):
    try:
        # Download historical data spanning long enough timeline to process 52w highs and 90-day index shifts safely
        chart_raw_data = yf.download(list(stocks_list), period="2y", interval="1d", progress=False)
        
        # Isolate individual ticker structures into isolated dataframes matching your setup logic
        ticker_dfs = {}
        for ticker in stocks_list:
            if len(stocks_list) > 1:
                t_df = pd.DataFrame({
                    'Open': chart_raw_data['Open'][ticker],
                    'High': chart_raw_data['High'][ticker],
                    'Low': chart_raw_data['Low'][ticker],
                    'Close': chart_raw_data['Close'][ticker],
                    'Volume': chart_raw_data['Volume'][ticker]
                }).dropna()
            else:
                t_df = chart_raw_data.dropna().copy()
            
            if not t_df.empty and len(t_df) >= 261:
                t_df["SMA_50"] = round(t_df['Close'].rolling(window=50).mean(), 2)
                t_df["SMA_200"] = round(t_df['Close'].rolling(window=200).mean(), 2)
                ticker_dfs[ticker] = t_df

        if not ticker_dfs:
            return pd.DataFrame()

        # Find valid chronological execution timeline dates matching trading sessions
        any_ticker = list(ticker_dfs.keys())[0]
        full_timeline = ticker_dfs[any_ticker].index
        
        # Calculate real data for the last 90 trading days to cover both charts
        days_to_compute = min(90, len(full_timeline))
        historical_records = []

        for i in range(days_to_compute - 1, -1, -1):
            target_idx = -1 - i
            current_date = full_timeline[target_idx]
            day_total_count = 0
            day_positive_count = 0
            
            for ticker, df_cloned in ticker_dfs.items():
                if len(df_cloned) < abs(target_idx) + 260:
                    continue
                
                # Dynamic calculations relative to the target index lookback offset
                c_close = df_cloned["Close"].iloc[target_idx]
                p_close = df_cloned["Close"].iloc[target_idx - 1] # Previous day close for gain tracking
                c_vol = df_cloned["Volume"].iloc[target_idx]
                ma_50 = df_cloned["SMA_50"].iloc[target_idx]
                ma_200 = df_cloned["SMA_200"].iloc[target_idx]
                
                # Handle safe range windows relative to chosen index shift pointer
                end_p = len(df_cloned) + target_idx
                ma_200_20 = df_cloned["SMA_200"].iloc[target_idx - 19] if end_p >= 20 else 0
                
                low_52w = round(min(df_cloned["Low"].iloc[target_idx - 260 : end_p if end_p != 0 else None]), 2)
                hist_end = len(df_cloned) + target_idx
                high_52w = round(df_cloned["High"].iloc[target_idx - 260 : hist_end].max(), 2)

                c1 = int(c_close > ma_50 > ma_200)
                c2 = int(ma_50 > ma_200)
                c3 = int(ma_200 > ma_200_20)
                c4 = int(ma_50 > ma_200)
                c5 = int(c_close > ma_50)
                c6 = int(c_close >= (1.3 * low_52w))
                c7 = int(c_close >= (0.75 * high_52w))
                c8 = int(c_close >= 20)
                c9 = int(c_vol > 20000)
                c10 = int((c_vol * c_close) > 2000000)

                if (c1 + c2 + c3 + c4 + c5 + c6 + c7 + c8 + c9 + c10) >= 10:
                    day_total_count += 1
                    if c_close > p_close:
                        day_positive_count += 1
            
            day_pos_pct = (day_positive_count / day_total_count * 100) if day_total_count > 0 else 0
            
            historical_records.append({
                "Date": current_date.strftime("%Y-%m-%d"), 
                "Total Count": day_total_count,
                "Positive Pct": round(day_pos_pct, 1)
            })

        return pd.DataFrame(historical_records)
    except Exception as e:
        return pd.DataFrame()

# Process full 90-day data asset
historical_df = compute_historical_know_counts(tuple(KNOWN_STOCKS))

# ==============================================================================
# 9. AUTOMATED BREADTH MARKET REGIME INTERPRETATION
# ==============================================================================
if not historical_df.empty and len(historical_df) >= 10:
    #st.markdown("#### 🧠 Market Breadth Regime Analysis")
    
    # Isolate trailing 30 days data (or max available) for trend analysis
    sample_df = historical_df.tail(30).copy()
    counts = sample_df["Total Count"].tolist()
    dates = sample_df["Date"].tolist()
    
    current_count = counts[-1]
    prev_count = counts[-2]
    
    # 1. Compute Basic Moving Averages of the Breadth Metric
    ma_short = np.mean(counts[-5:])  # 5-day breath trend
    ma_long = np.mean(counts[-20:])  # 20-day breadth trend
    
    # 2. Identify Peak/Trough Structures (Swing Highs / Lows)
    peaks = []
    troughs = []
    for idx in range(1, len(counts) - 1):
        if counts[idx] > counts[idx-1] and counts[idx] > counts[idx+1]:
            peaks.append((idx, counts[idx]))
        elif counts[idx] < counts[idx-1] and counts[idx] < counts[idx+1]:
            troughs.append((idx, counts[idx]))
            
    # 3. Formulate structural trend strings
    structure_desc = "Consolidating Range"
    if len(peaks) >= 2 and len(troughs) >= 2:
        if peaks[-1][1] > peaks[-2][1] and troughs[-1][1] > troughs[-2][1]:
            structure_desc = "Bullish Structure (Higher Highs & Higher Lows)"
        elif peaks[-1][1] < peaks[-2][1] and troughs[-1][1] < troughs[-2][1]:
            structure_desc = "Deteriorating Structure (Lower Highs & Lower Lows)"
        elif peaks[-1][1] < peaks[-2][1] and troughs[-1][1] > troughs[-2][1]:
            structure_desc = "Coiling / Symmetrical Compression"
            
    # 4. Determine Momentum & Direction Status Flags
    if ma_short > ma_long and current_count >= prev_count:
        status_color = "#00FF00" # Emerald Green
        status_title = "EXPANDING MOMENTUM"
        action_note = "Market participation is expanding actively. Growth setups have a high probability of immediate follow-through. Lean long."
    elif ma_short < ma_long and current_count <= prev_count:
        status_color = "#FF4B4B" # Red
        status_title = "DETERIORATING BREADTH"
        action_note = "Market leadership is thinning or experiencing distribution. New breakouts are prone to failure traps. Tighten risk parameters and trail stops aggressively."
    else:
        status_color = "#FFA500" # Orange
        status_title = "CHOPPY / TRANSITIONAL REGIME"
        action_note = "Breadth lacks a clear trend or is turning divergent. Prioritize high-conviction, isolated leaders showing clean relative strength; avoid chasing generic extensions."

    # 5. Render styled callout UI box
    st.markdown(
        f"""
        <div style="border: 1px solid {status_color}; border-left: 5px solid {status_color}; padding: 12px; border-radius: 4px; background-color: #1a1c23; margin-top: 10px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                <span style="font-weight: bold; color: {status_color}; font-size: 1.1em;">⚠️ MARKET STATUS: {status_title}</span>
                <span style="font-size: 0.9em; color: #888;">Structure: <b>{structure_desc}</b></span>
            </div>
            <p style="margin: 0; font-size: 0.95em; color: #e0e0e0; line-height: 1.5;">
                <b>Breadth Matrix:</b> Current active Minervini pool rests at 
                <b style="color: #FFD700;">{current_count}</b> setups 
                (5-Day Trend Avg: 
                <b style="color: #FFD700;">{ma_short:.1f}</b> 
                vs 20-Day Trend Avg: 
                <b style="color: #FFD700;">{ma_long:.1f}</b>). <br>
                <b>Tactical Playbook:</b> {action_note}
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )

#st.markdown("---")

#st.markdown(f"### Total Count ({know_total_count})")
if not historical_df.empty:
    # 1. THE ORIGINAL CHART: Updated to pass the full dataframe to show 90 days instead of 30
    st.line_chart(data=historical_df, x="Date", y="Total Count", use_container_width=True)
    
    #st.markdown("---")
    
    # 2. THE NEW STANDALONE CHART: Displays the Positive Percentage metric over 90 days
    #st.markdown(f"### Positive Percentage ({know_pos_pct:.1f}%)")
    #st.line_chart(data=historical_df, x="Date", y="Positive Pct", use_container_width=True)
else:
    st.info("Insufficient historical trading records available to draw historical metrics.")

st.markdown("---")

# ==============================================================================
# 11. MARKET REGIME REFERENCE TABLE (Dynamic Highlight)
# ==============================================================================
#st.markdown("---")
st.markdown(f"#### 🧭 Market Regime Reference ({pct_above_ema200:.2f}%)")
# 1. Define raw data exactly from your reference image
regime_data = {
    "Market Condition": [
        "Above 200 EMA < 40%",
        "Above 200 EMA 40–50%",
        "Above 200 EMA 50–60%",
        "Above 200 EMA > 60%",
        "Above 200 EMA > 70%"
    ],
    "What to do": [
        "Be cautious, focus only on best setups",
        "Recovery attempt",
        "Market improving",
        "Good swing trading environment",
        "Strong bull participation"
    ]
}

# 2. Convert to DataFrame
df_regime = pd.DataFrame(regime_data)

# 3. Determine which row index should be highlighted based on your live variable
# (Using nested if/elif structure matching the hierarchy)
highlight_idx = None

if pct_above_ema200 > 70:
    highlight_idx = 4
elif pct_above_ema200 > 60:
    highlight_idx = 3
elif 50 <= pct_above_ema200 <= 60:
    highlight_idx = 2
elif 40 <= pct_above_ema200 < 50:
    highlight_idx = 1
elif pct_above_ema200 < 40:
    highlight_idx = 0

# 4. Create a styling function to apply the lime background
def highlight_current_regime(row):
    style = [''] * len(row)

    if row.name == highlight_idx:

        # Be cautious = Light Red
        if highlight_idx == 0:
            bg = "#FFCCCC"

        # Recovery Attempt + Market Improving = Light Orange
        elif highlight_idx in [1, 2]:
            bg = "#FFD8A8"

        # Good / Strong market = Light Green
        else:
            bg = "#90EE90"

        style = [f'background-color: {bg}; color: #000000; font-weight: bold;'] * len(row)

    return style

# 5. Apply the style and render via Streamlit dataframe (handles styling better than st.table)
styled_df = df_regime.style.apply(highlight_current_regime, axis=1)

st.dataframe(
    styled_df, 
    use_container_width=True, 
    hide_index=True
)

st.markdown("---")

# --- Render Header with Inline Summary Metrics inside Parentheses ---
# header_html = (
#     f"<div style='margin-top:20px; font-size:1.15em; font-weight:bold; display:flex; align-items:center; gap:10px;'>"
#     f"<span>⭐ Minervini Qualified Stocks</span>"
#     f"<span style='font-weight:normal; color:#888;'> "
#     f"(<b style='color:#eee;'>Positive Pct:</b> {know_pos_pct:.1f}% |"
#     f" <b style='color:#eee;'>Positive Count:</b> {know_positive_count} |"
#     f" <b style='color:#eee;'>Total Count:</b> {know_total_count})"
#     f"</div>"
# )
# st.markdown(header_html, unsafe_allow_html=True)

st.markdown(
    f"#### ⭐ Minervini Qualified Stocks ("
    f"Positive Pct: {know_pos_pct:.1f}% | "
    f"Positive Count: {know_positive_count} | "
    f"Total Count: {know_total_count})"
)

if email_content_stocks or email_content_removed:
    minervini_html = ""
    
    # 1. Active Symbols Layout (Sorted Alphabetically by the ticker name)
    for sym, is_new_addition, is_positive_today in sorted(email_content_stocks, key=lambda x: x[0]):
        
        # Inject small up logo to the left side if the stock finished positive today
        up_logo = "<span style='color:#00FF00; margin-right:4px; font-weight:bold;'>▲</span>" if is_positive_today else ""
        
        if is_new_addition:
            minervini_html += f'<div class="ticker-badge new-pattern-badge">{up_logo}{sym}</div>'
        else:
            minervini_html += f'<div class="ticker-badge">{up_logo}{sym}</div>'
            
    # 2. Dropped/Removed Symbols Layout (Sorted Alphabetically with line-through)
    for sym in sorted(email_content_removed):
        minervini_html += f'<div class="ticker-badge removed-badge">{sym}</div>'
        
    st.markdown(minervini_html, unsafe_allow_html=True)
else:
    st.text("None")

st.markdown("---")

# ==============================================================================
# BLOCK B: NEW EXTRA 52W HIGH SYMBOLS (Placed directly underneath)
# ==============================================================================
#st.markdown("<br>", unsafe_allow_html=True) # Spacer

# active_52wk_high_count = len(extra_52wk_high_symbols)

# extra_header_html = (
#     f"<div style='font-size:1.15em; font-weight:bold; display:flex; align-items:center; gap:10px;'>"
#     f"<span>🚀 ATH , but fail Minervini criteria</span>"
#     f"<span style='font-weight:normal; color:#ffffff;'>({active_52wk_high_count})</span>"
#     f"</div>"
# )
# st.markdown(extra_header_html, unsafe_allow_html=True)

st.markdown(f"#### 🚀 ATH , but fail Minervini criteria ({len(extra_52wk_high_symbols)})")
# Render if there are either active items OR removed items to show
if extra_52wk_high_symbols or extra_52wk_high_removed:
    extra_html = ""
    
    # 1. Render Active Symbols (Sorted alphabetically)
    for sym, is_new_addition_52w in sorted(extra_52wk_high_symbols, key=lambda x: x[0]):
        if is_new_addition_52w:
            # Uses your exact native gold badge class for brand new additions today
            extra_html += f'<div class="ticker-badge new-pattern-badge">{sym}</div>'
        else:
            # Standard dark badge layout for stocks that were already on this list yesterday
            extra_html += f'<div class="ticker-badge">{sym}</div>'
            
    # 2. Append Removed Symbols (Sorted alphabetically with the removed badge style)
    for sym in sorted(extra_52wk_high_removed):
        extra_html += f'<div class="ticker-badge removed-badge">{sym}</div>'
        
    st.markdown(extra_html, unsafe_allow_html=True)
else:
    st.text("None")

#st.markdown("<br>", unsafe_allow_html=True) # Spacer
st.markdown("---")

# --- 1. TWO BOTAK (Full Horizontal Row) ---
st.markdown(f"#### 🔥 Two Botak = Awareness short term group burst ({len(b_list)})")
if b_list or b_yest:
    html_b = ""
    for sym in b_list:
        cls = "new-pattern-badge" if sym not in b_yest else ""
        html_b += f'<div class="ticker-badge {cls}">{sym}</div>'
    
    # Process and append removed stocks
    removed_b = [sym for sym in b_yest if sym not in b_list]
    for sym in sorted(removed_b):
        html_b += f'<div class="ticker-badge removed-badge">{sym}</div>'
        
    st.markdown(html_b, unsafe_allow_html=True)
else:
    st.info("No active setups discovered.")

#st.markdown("<br>", unsafe_allow_html=True) # Spacer
#st.markdown("---")
st.write("")

# ===================== TWO BOTAK 60-DAY BREADTH CHART =====================
if not two_botak_hist.empty:
    #st.markdown("#### 📊 Two Botak Breadth (60 Days)")
    st.bar_chart(
        data=two_botak_hist,
        x="Date",
        y="Two Botak Count",
        use_container_width=True
    )

st.markdown("---")

# --- 3. BULLISH ENGULFING (Full Horizontal Row Below Tight PPP) ---
total_engulf = len(e2_list) + len(e3_list)
st.markdown(f"#### 🐳 Bullish Engulfing = Awareness HL ({total_engulf})")

if e2_list or e3_list or e2_yest or e3_yest:
    if e2_list or e2_yest:
        st.markdown(f"**2x Engulfing Conditions Matched ({len(e2_list)}):**")
        html_e2 = ""
        for sym in e2_list:
            cls = "new-pattern-badge" if sym not in e2_yest else ""
            html_e2 += f'<div class="ticker-badge {cls}">{sym}</div>'
        
        # Process and append removed 2x engulfing stocks
        removed_e2 = [sym for sym in e2_yest if sym not in e2_list]
        for sym in sorted(removed_e2):
            html_e2 += f'<div class="ticker-badge removed-badge">{sym}</div>'
            
        st.markdown(html_e2, unsafe_allow_html=True)
    
    st.write("")
    if e3_list or e3_yest:
        st.markdown(f"<div style='margin-top:10px;'><b>3x Engulfing Conditions Matched ({len(e3_list)}):</b></div>", unsafe_allow_html=True)
        html_e3 = ""
        for sym in e3_list:
            cls = "new-pattern-badge" if sym not in e3_yest else ""
            html_e3 += f'<div class="ticker-badge {cls}">{sym}</div>'
            
        # Process and append removed 3x engulfing stocks
        removed_e3 = [sym for sym in e3_yest if sym not in e3_list]
        for sym in sorted(removed_e3):
            html_e3 += f'<div class="ticker-badge removed-badge">{sym}</div>'
            
        st.markdown(html_e3, unsafe_allow_html=True)
else:
    st.info("No active setups discovered.")

st.write("")
if not engulf_hist.empty:
    #st.markdown("#### 🐳 2x Engulfing Breadth (60 Days)")
    st.bar_chart(engulf_hist, x="Date", y="2x Engulfing Count", use_container_width=True)

    #st.markdown("#### 🐳 3x Engulfing Breadth (60 Days)")
    st.bar_chart(engulf_hist, x="Date", y="3x Engulfing Count", use_container_width=True)

# --- EXTRA TREND METRICS (Stacked Horizontally Below Patterns) ---
#st.markdown("---")
#st.markdown("### 📊 Extra Trend Metrics (PowerTrend Indicators)")
#st.markdown("<br>", unsafe_allow_html=True) # Spacer
st.markdown("---")

# --- 4. POWERTREND (Full Horizontal Row) ---
st.markdown(f"#### ⚡ PowerTrend = Awareness thematic leaders extended ({len(pt_list)})")
if pt_list or pt_yest:
    html_pt = ""
    for sym in pt_list:
        cls = "new-pattern-badge" if sym not in pt_yest else ""
        html_pt += f'<div class="ticker-badge {cls}">{sym}</div>'
    
    # Process and append removed stocks
    removed_pt = [sym for sym in pt_yest if sym not in pt_list]
    for sym in sorted(removed_pt):
        html_pt += f'<div class="ticker-badge removed-badge">{sym}</div>'
        
    st.markdown(html_pt, unsafe_allow_html=True)
else:
    st.text("None")

#st.markdown("<br>", unsafe_allow_html=True) # Spacer
st.markdown("---")

# --- 5. POWERTREND NOT EXTENDED (Full Horizontal Row Below PowerTrend) ---
st.markdown(f"#### ⚡ PowerTrend ... Not Extended ({len(ptne_list)})")
if ptne_list:
    html_ptne = ""
    for sym in ptne_list:
        cls = "new-pattern-badge" if sym not in ptne_yest else ""
        html_ptne += f'<div class="ticker-badge {cls}">{sym}</div>'
    st.markdown(html_ptne, unsafe_allow_html=True)
else:
    st.text("None")

#st.markdown("<br>", unsafe_allow_html=True) # Spacer
st.markdown("---")

# --- 6. VALUE TRAP (Full Horizontal Row Below PowerTrend Not Extended) ---
st.markdown(f"#### ⚠️ Value Trap ({len(vt_list)})")
if vt_list or vt_yest:
    html_vt = ""
    for sym in vt_list:
        cls = "new-pattern-badge" if sym not in vt_yest else ""
        html_vt += f'<div class="ticker-badge {cls}">{sym}</div>'
    
    # Process and append removed stocks
    removed_vt = [sym for sym in vt_yest if sym not in vt_list]
    for sym in sorted(removed_vt):
        html_vt += f'<div class="ticker-badge removed-badge">{sym}</div>'
        
    st.markdown(html_vt, unsafe_allow_html=True)
else:
    st.text("None")

st.markdown("---")

# --- 2. TIGHT PPP (Full Horizontal Row Below Two Botak) ---
st.markdown(f"#### 📉 PPP = Opportunity ({len(ppp_list)})")
if ppp_list or ppp_yest:
    html_p = ""
    for sym in ppp_list:
        cls = "new-pattern-badge" if sym not in ppp_yest else ""
        html_p += f'<div class="ticker-badge {cls}">{sym}</div>'
    
    # Process and append removed stocks
    removed_ppp = [sym for sym in ppp_yest if sym not in ppp_list]
    for sym in sorted(removed_ppp):
        html_p += f'<div class="ticker-badge removed-badge">{sym}</div>'
        
    st.markdown(html_p, unsafe_allow_html=True)
else:
    st.info("No active setups discovered.")

#st.markdown("<br>", unsafe_allow_html=True) # Spacer
#st.markdown("---")

#st.write(f"Percentage of stock above EMA200: {pct_above_ema200:.2f}%")

