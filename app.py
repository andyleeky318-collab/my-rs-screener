import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import time
from google import genai
import plotly.graph_objects as go
import streamlit.components.v1 as components

_timing_log = {}  # module-level dict, accumulates across all call sites
_latest_bar_dropped = False

def timed(label, fn, *args, **kwargs):
    """Call fn(*args, **kwargs), record elapsed ms in _timing_log, return result."""
    t0 = time.perf_counter()
    result = fn(*args, **kwargs)
    elapsed = (time.perf_counter() - t0) * 1000
    _timing_log[label] = elapsed
    return result

# 1. Setup Streamlit Page
st.set_page_config(page_title="Chrome Sector RS", layout="wide")
#st.title("🐱 Theme Tracker")

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
    '3D Printing': ['XMTR', 'VELO', 'DDD', 'PRLB', 'MTLS', 'SSYS', 'NNDM'],
    'Crypto': ['MSTR', 'CRCL', 'COIN', 'IBIT'],
    'Nuclear': ['URA', 'NLR', 'CEG', 'CCJ', 'OKLO', 'UUUU', 'SMR', 'LEU'],
    'MAG7': ['MAGS', 'AAPL', 'GOOGL', 'NVDA', 'META', 'MSFT', 'AMZN', 'TSLA'],
    'ETF': ['XLK', 'XLF', 'XLE', 'XLP', 'XLU', 'XLI', 'XLY', 'XLV', 'XLC', 'XLB'],
    'SPACE': ['SPCX', 'UFO', 'VSAT', 'RKLB', 'SATL', 'RDW', 'LUNR', 'BKSY', 'PL', 'IRDM', 'SATS', 'GSAT', 'ASTS', 'ARKX', 'FLY', 'SPCE', 'KRMN', 'SIDU'],
    'CATHIE WOOD': ['ARKG', 'ARKK', 'ARKQ', 'ARKW', 'ARKF', 'ARKX'],
    'CHINA': ['FUTU', 'LI', 'KWEB', 'XPEV', 'NIO', 'PDD', 'BIDU', 'JD', 'BABA'],
    'DATA CENTER / AI HOST': ['WGMI', 'CRWV', 'NBIS', 'IREN', 'WULF', 'CORZ', 'CIFR', 'HUT', 'BTDR'],
    'SOLAR': ['TAN', 'SEDG', 'ENPH', 'FSLR', 'ARRY', 'SHLS', 'CSIQ', 'RUN', 'DQ'],
    'COML SVCS-ADVRTSNG': ['OMC', 'DJT'],
    'AEROSPACE/DEFENSE': ['SHLD', 'RTX', 'LMT', 'HON', 'BA', 'NOC', 'KTOS'],
    #'AEROSPACE/DEFENSE': ['ITA', 'RTX', 'LMT', 'HON', 'BA', 'NOC', 'TDG', 'LHX', 'HWM', 'AXON', 'HEI', 'LDOS', 'TDY', 'TXT', 'FTAI', 'CW', 'BWXT', 'HII', 'CR', 'DRS', 'LOAR', 'AVAV', 'HXL', 'KTOS', 'MIR', 'OSIS', 'AIR', 'MRCY'],
    'AGRICULTURAL OPRTIONS': ['ADM', 'BG', 'PPC', 'CALM', 'SEB'],
    'TRNSPRT-AIR FREIGHT': ['UPS', 'FDX'],
    'TRANSPORTATION-SVCS': ['DASH', 'EXPD', 'CHRW', 'CART', 'GXO', 'HUBG', 'UBER', 'PFGC', 'SARO', 'VNT', 'VRRM', 'CAAP'],
    'TRNSPRTTIN-AIRLNE': ['JETS', 'DAL', 'UAL', 'LUV', 'AAL', 'ALK', 'CPA', 'SKYW'],
    'ENERGY-ALT/OTHER': ['BIP', 'TLN', 'CWEN', 'BEPC'],
    'MINING-METAL ORES': ['PICK', 'AA', 'SCCO', 'FCX', 'CCJ', 'CRS', 'ATI', 'TECK', 'CENX', 'AG', 'HL', 'NEM', 'KALU', 'CSTM'],
    'APPAREL-SHOES & REL': ['NKE', 'DECK', 'ONON', 'RL', 'BIRK', 'CROX', 'LEVI', 'VFC', 'GIL', 'PVH', 'COLM', 'KTB', 'SHOO'],
    'RETAIL-APPRL/SHOES/ACC': ['TJX', 'ROST', 'BURL', 'TPR', 'GAP', 'ANF', 'BBWI', 'CPRI', 'BOOT', 'AEO', 'URBN', 'CRI', 'BKE', 'VSXY'],
    'AUTO/TRCK-ORGNL EQP': ['ITW', 'CMI', 'APTV', 'ITT', 'DCI', 'ALSN', 'ALV', 'GNTX', 'LEA', 'BC', 'ATMU', 'VC', 'BWA'],
    'AUTO/TRCK-RPLC PRTS': ['LKQ', 'DORM', 'AAP'],
    'BEVERAGES-ALCOHOLIC': ['STZ', 'TAP', 'SAM'],
    'BEV-NON-ALCOHOLIC': ['KO', 'MNST', 'CCEP', 'COKE', 'BRBR', 'CELH', 'FIZZ'],
    'MEDICAL-BIOMED/BTH': ['BNTX', 'AMGN', 'GILD', 'MRNA', 'ILMN', 'SMMT', 'PCVX', 'BMRN', 'TECH', 'NUVL', 'ELAN', 'HALO', 'RNA', 'KRYS', 'ADMA', 'BBIO', 'IMVT', 'ACLX', 'AXSM', 'CRSP', 'DNLI', 'ALVO', 'APGE', 'DYN', 'RYTM', 'KYMR', 'EWTX', 'PTGX', 'TWST', 'TXG', 'CGON', 'JANX', 'ARWR', 'VERA', 'NVAX', 'CLDX'],
    'MEDIA-RADIO/TV': ['FOX', 'SIRI', 'NXST'],
    'TELCOM-SVC-CBL/SAT': ['CMCSA', 'CHTR'],
    'LEISRE-GAMNG/EQUIP': ['BETZ', 'FLUT', 'LVS', 'MGM', 'WYNN', 'CZR', 'LNW', 'BYD', 'RSI', 'DKNG', 'CHDN', 'PENN'],
    'CHEMICALS-FERTILIZERS': ['NTR', 'CTVA', 'CF', 'MOS', 'FMC', 'SMG'],
    'CHEMICALS-BASIC': ['DD', 'ESI', 'AVNT', 'HUN', 'IOSP', 'DOW', 'LYB', 'WLK', 'AVTR', 'CE', 'EMN', 'CC'],
    'CHEMICALS-SPECIALTY': ['LIN', 'ECL', 'APD', 'ALB', 'CBT', 'NEU', 'KWR', 'HWKN', 'MTX', 'TROX', 'OLN', 'FUL', 'WDFC', 'AZZ', 'UFPT'],
    'ENERGY COAL': ['HCC', 'BTU', 'ARLP', 'AMR'],
    'MEDIA-DIVERSIFIED': ['WMG', 'SPOT', 'LYV', 'DIS', 'WBD'],
    'COMPTER-NETWRKING': ['ANET', 'CSCO', 'CALX'],
    'COMPTR-DATA STRGE': ['DRAM', 'EWY', 'WDC', 'STX', 'MU', 'SNDK'],
    'CMP-HRDWRE/PERIP': ['DELL', 'HPQ', 'SMCI', 'HPE', 'ZBRA', 'NATL'],
    'CONTAINERS/PACKAGING': ['SW', 'BALL', 'PKG', 'AVY', 'AMCR', 'OC', 'CCK', 'ATR', 'GPK', 'SLGN', 'SON', 'GEF', 'OI'],
    'OIL&GAS-DRILLING': ['SLB', 'BKR', 'NE', 'VAL', 'HP', 'SDRL'],
    'BLDG-CMENT/CNCRT': ['CRH', 'MLM', 'VMC', 'EXP', 'KNF', 'USLM'],
    'CMPTER-TECH SRVCS': ['PAYX', 'MSCI', 'VRSK', 'TYL', 'GDDY', 'J', 'FDS', 'AKAM', 'DBX', 'EXLS', 'KD', 'MARA', 'EEFT', 'DXC', 'CORZ', 'AVPT', 'ACN', 'CTSH', 'CDW', 'CACI', 'PSN', 'EPAM', 'DOX', 'KBR', 'GLOB', 'NSIT', 'SAIC', 'ASGN'],
    'RETAIL-DPRTMNT STRS': ['DDS', 'M', 'KSS'],
    'RETAIL-DISCNT&VARI': ['DG', 'DLTR', 'FIVE', 'OLLI'],
    'RETAIL-DRUG STORES': ['CVS', 'UNH', 'ELV', 'HUM'],
    'UTILITY-ELCTRIC PWR': ['NEE', 'SO', 'CEG', 'DUK', 'AEP', 'SRE', 'D', 'VST', 'PEG', 'PCG', 'EXC', 'XEL', 'ED', 'EIX', 'WEC', 'ETR', 'DTE', 'FE', 'PPL', 'AEE', 'ES', 'CMS', 'NRG', 'CNP', 'LNT', 'EVRG', 'AES', 'PNW', 'OGE', 'IDA', 'POR', 'ORA', 'BKH', 'TXNM', 'NWE', 'MGEE'],
    'ELEC-POWER/EQPMT': ['GRID', 'ETN', 'ABBN', 'GEV', 'AME', 'ROK', 'HUBB', 'RRX', 'GNRC', 'AYI', 'BDC', 'ENS', 'FLNC', 'SMR', 'ATKR', 'PBW', 'POWL', 'VICR', 'BE', 'ENVX'],
    'TELCOM-FIBR OPTCS': ['XTL', 'AAOI', 'COHR', 'CIEN', 'FN', 'LITE', 'AXTI'],
    'ELEC-PARTS': ['APH', 'GLW', 'NVT', 'CAMT', 'TEL'],
    'ELEC-SCNTIFIC/MSRNG': ['PH', 'EMR', 'KEYS', 'FTV', 'CGNX', 'NOVT', 'ST', 'NXT', 'ITRI', 'ESE', 'SXI', 'MTRN'],
    'ELEC-SEMICNDCTR EQP': ['EUV', 'ASML', 'KLAC', 'AMAT', 'LRCX', 'ONTO', 'NVMI', 'TER', 'AEIS', 'MKSI', 'ENTG', 'ACLS', 'AEHR'],
    'ELEC-CONTRACT MFG': ['CLS', 'SOLS', 'VRT', 'FLEX', 'PLXS', 'JBL', 'SANM', 'TTMI'],
    'ELEC-MISC PRODUCTS': ['OLED', 'LFUS', 'VSH'],
    'WHOLESALE-ELECT': ['SNX', 'ARW', 'AVT', 'REZI', 'GWW', 'FAST', 'FERG', 'GPC', 'POOL', 'AIT', 'WCC', 'MSM', 'UGI'],
    'RETAIL-CNSMR ELEC': ['BBY', 'GME'],
    'CONSUMER PROD-ELEC': ['SN', 'ROKU', 'WHR', 'SPB'],
    'BLDG-HEAVY CONSTR': ['PWR', 'IESC', 'EME', 'FIX', 'ACM', 'TTEK', 'MTZ', 'APG', 'FLR', 'DY', 'STRL', 'ROAD', 'GVA', 'PRIM'],
    'BLDG-RSIDNT/COMML': ['ITB', 'BLD', 'IBP', 'EXPO', 'DHI', 'LEN', 'NVR', 'PHM', 'TOL', 'MTH', 'TMHC', 'KBH', 'SKY', 'MHO', 'TPH', 'FTDR', 'GRBK', 'DFH', 'CCS', 'LGIH'],
    'BLDG-MBILE/MFG & RV': ['CVCO', 'PATK'],
    'POLLUTION CONTROL': ['WM', 'RSG', 'CLH', 'CWST'],
    'COMML SVCS-LEASING': ['URI', 'AER', 'UHAL', 'WSC', 'R', 'HRI', 'WD', 'CAR', 'MGRC', 'PRG'],
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
    'LEISURE-LODGING': ['PEJ', 'MAR', 'HLT', 'RCL', 'CCL', 'VIK', 'H', 'NCLH', 'MTN', 'WH', 'CHH', 'RRR', 'TNL', 'VAC'],
    'COSMETICS/PERSNL CRE': ['PG', 'CL', 'KMB', 'KVUE', 'EL', 'CHD', 'CLX', 'ELF', 'IPAR'],
    'SOAP & CLNG PREPARAT': ['REYN', 'ENR'],
    'DVRSIFIED OPRTIONS': ['MMM', 'RLX', 'WMS', 'AWI', 'BRC', 'YETI', 'LCII'],
    'MCHNRY-GEN INDSTRL': ['GE', 'TT', 'CARR', 'JCI', 'IR', 'XYL', 'DOV', 'LII', 'PNR', 'IEX', 'GGG', 'NDSN', 'LECO', 'WWD', 'AAON', 'FLS', 'MIDD', 'MOD', 'WTS', 'BMI', 'ZWS', 'ESAB', 'TKR', 'GTLS', 'GTES', 'FELE', 'KAI', 'MWA', 'NPO', 'CXT', 'OII', 'SYM'],
    'CHEMICALS-PAINTS': ['SHW', 'PPG', 'RPM', 'AXTA'],
    'COMPTER SFTWR-SCRITY': ['CIBR', 'FTNT', 'PANW', 'CRWD', 'CHKP', 'RBRK', 'RPD', 'OKTA', 'ZS', 'TENB'],
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
    'OIL&GAS INTEGRATED': ['USO', 'XOM', 'CVX', 'OXY'],
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
    'BANKS-SOUTHEAST': ['KBE', 'FNB', 'FBK', 'HOMB', 'OZK', 'ABCB'],
    'BANKS-MIDWEST': ['KRE', 'FFIN', 'UMBF', 'ASB', 'FULT', 'CBU', 'SFNC', 'FRME', 'NBTB', 'CBSH', 'COLB', 'GBCI', 'UBSI', 'HWC', 'TOWN'],
    'BANKS-NORTHEAST': ['IAT', 'FCNCA', 'EWBC', 'FHN', 'CFR', 'PNFP', 'SSB', 'WTFC', 'BPOP', 'PB', 'WU', 'EBC', 'FBP', 'TBBK'],
    'FINANC-SVINGS & LO': ['WBS', 'TFSL', 'WSFS', 'PFS'],
    'MED-MANAGED CARE': ['UNH', 'ELV', 'CI', 'CNC', 'HUM', 'MOH', 'OSCR', 'ALHC'],
    'TRANSPORTATION-SHIP': ['KEX', 'FRO', 'MATX', 'GLNG', 'STNG', 'TDW', 'INSW', 'SBLK', 'ZIM', 'TNK'],
    'MDCAL-WHLSLE DRG': ['MCK', 'COR', 'CAH', 'HSIC'],
    'MEDICAL-PRODUCTS': ['TMO', 'ABT', 'DHR', 'A', 'IDXX', 'RMD', 'MTD', 'RVTY', 'BRKR', 'QGEN', 'BIO', 'LNTH', 'MASI', 'GKOS', 'BLCO', 'MMSI'],
    'MEDICAL-SYSTEMS/EQP': ['IHI', 'ISRG', 'SYK', 'BSX', 'MDT', 'BDX', 'GEHC', 'EW', 'DXCM', 'STE', 'WST', 'COO', 'ZBH', 'WAT', 'BAX', 'ALGN', 'PODD', 'NTRA', 'TFX', 'PEN', 'INSP'],
    'METAL PROC & FABRICA': ['RBC', 'MLI', 'VMI', 'ROCK'],
    'CMML SVCS-CNSLTNG': ['TNET', 'LOPE', 'CNXC', 'ABM', 'LAUR', 'QXO', 'G'],
    'AUTO MANUFACTURERS': ['TSLA', 'GM', 'F', 'RIVN'],
    'TRNSPRT-EQP MFG': ['OSK', 'HOG', 'WAB', 'TEX', 'TRN', 'ALG'],
    'LEISRE-MVIES & REL': ['DIS', 'LYV', 'FWONA', 'TKO', 'MSGS', 'FUN', 'CNK', 'PRKS', 'MANU', 'BATRA'],
    'INSRNCE-DIVRSIFIED': ['PGR', 'AFL', 'MET', 'ACGL', 'HIG', 'CINF', 'RGA', 'CNA', 'UNM', 'KNSL', 'GL', 'RLI', 'AXS', 'BWIN', 'ACT', 'FG', 'WTM', 'CNO'],
    'OFFICE SUPPLIES MFG': ['HNI', 'MLKN', 'ACCO'],
    'OIL&GAS-TRNSPRT/PIP': ['EPD', 'WMB', 'ET', 'OKE', 'KMI', 'MPLX', 'LNG', 'WES', 'PAA', 'DTM', 'KNTK', 'AM', 'SOBO', 'PAGP', 'DKL'],
    'OIL&GAS-RFING/MKT': ['PSX', 'MPC', 'VLO', 'DINO', 'IEP', 'PBF', 'CVI', 'SUN'],
    'OIL&GAS-FIELD SERVIC': ['HAL', 'WFRD', 'NOV', 'WHD', 'AROC', 'LBRT', 'USAC', 'KGS', 'AESI'],
    'LEISURE-SERVICES': ['CTAS', 'ROL', 'SCI', 'HRB', 'PLNT', 'LTH', 'VVV', 'GHC', 'UNF', 'LRN', 'DRVN', 'STRA'],
    'CONSUMR PROD-SPECI': ['MSA', 'HAS', 'AS', 'MAT', 'THO', 'PII', 'GOLF', 'HAYW', 'SIG'],
    'CMP SFTWR-SPC-ENTR': ['TTD', 'MGNI', 'PUBM'],
    'MEDICAL-ETHICAL DRGS': ['NVO', 'LLY', 'JNJ', 'ABBV', 'MRK', 'PFE', 'VRTX', 'REGN', 'BMY', 'ZTS', 'ALNY', 'BIIB', 'RPRX', 'UTHR', 'VTRS', 'INCY', 'INSM', 'SRPT', 'NBIX', 'ROIV', 'RGEN', 'VKTX', 'EXEL', 'JAZZ', 'CYTK', 'IONS', 'BHVN', 'RARE', 'CORT', 'MDGL', 'OGN', 'ALKS', 'CRNX', 'TGTX', 'PHB', 'PRGO', 'APLS', 'RVMD'],
    'MINING-GLD/SILVR/GMS': ['NEM', 'RGLD', 'AEM', 'AU', 'WPM', 'KGC', 'AGI', 'EGO'],
    'INSRNCE-PRP/CAS/TITL': ['BRK-B','CB', 'TRV', 'ALL', 'AIG', 'ERIE', 'WRB', 'MKL', 'L', 'EG', 'RNR', 'AFG', 'AIZ', 'MTG', 'SIGI', 'THG', 'KMPR', 'HGTY', 'MCY', 'NMIH', 'PLMR', 'SPNT', 'FNF', 'ORI', 'ESNT', 'FAF', 'RDN', 'AGO'],
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
    'TELECOM SVCS-FOREIGN': ['CCOI', 'LBTYA'],
    'TELCOM-INFRASTR': ['SATS', 'ASTS', 'IRDM'],
    'STEEL-PRODUCERS': ['SLX', 'NWPX', 'PKX', 'NUE', 'STLD', 'WS', 'RS', 'ASTL', 'CLF', 'GGB', 'CMC', 'RIO', 'TX', 'MTUS', 'MT', 'HCC', 'MSB', 'VALE', 'SID'],
    'TELCOM-CONS PROD': ['MSI', 'GRMN', 'UI'],
    #'TEXTILES': ['AIN', 'CULP', 'UFI'],
    'TOBACCO': ['PM', 'MO'],
    'BLDG-HAND TOOLS': ['SWK', 'SNA'],
    'TRNSPORTATION-TRCK': ['XTN', 'ODFL', 'JBHT', 'XPO', 'SAIA', 'KNX', 'LSTR', 'SNDR', 'ARCB', 'WERN'],
    'MACHINERY-FARM': ['DE', 'CNH', 'TTC', 'AGCO', 'SITE', 'FSS', 'ACA'],
    'MCHNRY-CNSTR/MNG': ['CAT', 'PCAR', 'LGN', 'ICHR', 'UCTT'],
    'UTILITY-WATER SUPPLY': ['AWK', 'WTRG', 'AWR', 'CWT'],
    'TELCOM SVC-WIRLES': ['TMUS', 'VZ', 'T', 'LBRDA', 'TIGO', 'TDS'],
    'ELEC-SEMICON FBLSS': ['SMH', 'SIMO', 'ARM', 'NVDA', 'AVGO', 'AMD', 'QCOM', 'ADI', 'MRVL', 'NXPI', 'MPWR', 'MCHP', 'ON', 'SWKS', 'QRVO', 'ALAB', 'CRDO', 'MTSI', 'LSCC', 'CRUS', 'PI', 'RMBS', 'SITM', 'ALGM', 'SLAB', 'POWI', 'IPGP', 'SMTC', 'DIOD', 'SYNA', 'AMBA'],
    'ELEC-SEMICON FNDRY': ['TSM', 'TXN', 'INTC', 'GFS', 'AMKR', 'TSEM', 'FORM', 'STM'],
    'ROBOTIC': ['AMBA', 'ARBE', 'MBLY', 'NOVT', 'HLX', 'JOBY', 'CGNX', 'ZBRA', 'CRNC', 'ROK', 'RR', 'PRCT', 'PTC', 'NDSN', 'HSAI', 'EMR', 'SERV', 'AVAV', 'TER', 'IPGP', 'TRMB', 'SYM'],
    'RARE EARTH': ['REMX', 'RARE', 'USAR', 'METC', 'TMC', 'MP', 'MOS', 'CRML', 'NB', 'PPTA', 'UAMY'],
    'QUANTUM': ['QNT', 'QTUM', 'QMCO', 'IONQ', 'QUBT', 'QBTS', 'RGTI', 'BTQ', 'ARQQ', 'INFQ', 'XNDU'],
    'FUEL CELL': ['FCEL', 'BLDP', 'HYDR', 'BE', 'PLUG'],
    'LITHIUM': ['LIT', 'LAC', 'SLI', 'SQM', 'ALB', 'ATLX'],
    'EUROPE': ['ENOR', 'EFNL', 'EWN', 'EWI', 'EWL', 'EDEN', 'EWO', 'EIRL', 'EWK', 'EWG', 'IEUR', 'EPOL', 'IEV', 'EWU', 'EWP', 'EWQ', 'EWD'],
    'BRAZIL': ['GGB', 'ABEV', 'PBR', 'UGP', 'VALE', 'SID', 'SUZ', 'VIV', 'MELI', 'BSBR', 'CSAN', 'ITUB', 'CIG', 'BBD', 'TIMB', 'XP', 'PAGS', 'INTR', 'SBS'],
    'ARGENTINA': ['ARGT', 'YPF', 'PAM', 'TGS', 'TEO', 'LOMA', 'CRESY', 'CEPU', 'BBAR', 'BMA', 'EDN', 'GGAL', 'IRS', 'SUPV'],
    'CANNABIS': ['CNBS', 'GRWG', 'MSOS', 'IIPR', 'CRON', 'HITI', 'SNDL', 'ACB', 'VFF', 'CGC', 'TLRY', 'OGI'],
    'DRONES': ['RDW', 'JOBY', 'UMAC', 'GD', 'TXT', 'ONDS', 'ACHR', 'LMT', 'DPRO', 'LHX', 'ESLT', 'AVAV', 'NOC', 'EH', 'KTOS', 'PRZO', 'RCAT', 'ZENA'],
    'PRECIOUS METAL': ['GLD', 'SLV', 'PPLT', 'GDX', 'SIL', 'RGLD'],
}

# Cleaned Known Stocks List Reference Array
KNOWN_STOCKS = [
    'HBMX', 'PWR', 'EUV', 'GRID', 'MAGS', 'SPCX', 'IBM', 'ELV', 'OSCR', 'QNT', 'HYDR', 'ALGM', 'LGN', 'IESC', 'AEHR', 'ACLS', 'MKSI', 'SMTC', 'AMKR', 
    'LSCC', 'DIOD', 'POWI', 'AA', 'ABBV', 'ALAB', 'AMGN', 'APO', 'BOTZ', 'CRCL', 'CRWV', 'D', 'DRAM', 'DUK', 'EEM', 'EWJ', 'EWY', 'EXC', 'FIGR', 
    'GEV', 'GILD', 'GXC', 'JEF', 'KMI', 'KRMN', 'LIN', 'MNST', 'NASA', 'NEM', 'NTR', 'NTAP', 'OR', 
    'OWL', 'Q', 'QQQ', 'RNG', 'RKT', 'SCCO', 'SHLD', 'SO', 'SOLS', 'SPMO', 'SPY', 'SPHB', 'TSEM', 'UNP', 'VTV', 
    'VUG', 'WGMI', 'WMB', 'XEL', 'XMAG', 'XYZ', 'ZIM','VICR', 'SLX', 'CBOE', 'SIMO', 'FLEX', 'POWL', 'VLO', 'DOCN', 
    'IYZ', 'LNG', 'AAOI', 'AXTI', 'TSEM', 'USO', 'JNJ', 
    'HP', 'GLD', 'ALB', 'BUG', 'BX', 'DOW', 'VZ', 'REMX', 'GDX', 'SIL', 'VEEV', 'SNDK', 'TLT', 'APH', 'ARM', 'FANG', 
    'NBIS', 'NVT', 'OXY', 'FORM', 'IBIT', 'QTUM', 'IAI', 'KWEB', 'IHI', 'UFO', 'ITA', 'IYT', 'CVS', 'HUM', 'NEE', 
    'HPE', 'PLAB', 'INOD', 'TTMI', 'CCJ', 'BE', 'SLV', 'PICK', 'COPX', 'MAR', 'XAR', 'VSXY', 'GLW', 'ANF', 'AEO', 
    'AEP', 'GH', 'SANM', 'ROK', 'PSN', 'IAT', 'HROW', 'PL', 'AVAV', 'CIEN', 'COHR', 'NU', 'WULF', 'IREN', 'CIFR', 
    'RDW', 'PH', 'LITE', 'ACHR', 'CACI', 'CRS', 'URA', 'NVO', 'NLR', 'ITB', 'MVST', 'EOSE', 'APP', 'RKLB', 'ASTS', 
    'IONQ', 'RMBS', 'RTX', 'NOC', 'LMT', 'HON', 'ONDS', 'CLS', 'LEU', 'VRT', 'VST', 'NRG', 'CEG', 'SMCI', 'CRDO', 
    'SOFI', 'XLP', 'XLE', 'HIMS', 'HOOD', 'GEV', 'XLV', 'HACK', 'XOP', 'CIBR', 'ICLN', 'XLB', 'XLU', 'XLRE', 'IGV', 
    'XLF', 'IPAY', 'XLC', 'XLI', 'KRE', 'XLK', 'CLOU', 'KBE', 'XME', 'XTL', 'JETS', 'SMH', 'XLY', 'XHB', 
    'XBI', 'XRT', 'MJ', 'META', 'MSFT', 'AAPL', 'AMZN', 'GOOGL', 'NVDA', 'TSLA', 'ARKX', 'ARKQ', 'ARKF', 
    'ARKW', 'ARKK', 'ARKG', 'CCL', 'RCL', 'UAL', 'BA', 'DAL', 'NCLH', 'AAL', 'LUV', 'PINS', 'SNAP', 
    'IBKR', 'SCHW', 'JPM', 'MS', 'GS', 'BAC', 'WFC', 'SPGI', 'BLK', 'NDAQ', 'C', 'LI', 'BIDU', 'NIO', 'XPEV', 
    'BABA', 'PDD', 'JD', 'DQ', 'JKS', 'ENPH', 'FSLR', 'TAN', 'SEDG', 'CSIQ', 'SPWR', 'RUN', 'PBW', 'CLX', 'PG', 
    'EL', 'LULU', 'SBUX', 'NKE', 'MELI', 'EBAY', 'FDX', 'UPS', 'SE', 'JMIA', 'ETSY', 'SHOP', 
    'Z', 'OPEN', 'CHWY', 'CVNA', 'BARK', 'GM', 'BLNK', 'QS', 'F', 'RIVN', 'FCEL', 'CHPT', 'LCID', 
    'UPST', 'PYPL', 'AFRM', 'V', 'MA', 'AXP', 'BITO', 'COIN', 'RIOT', 'MARA', 'MSTR', 'SI', 
    'DKNG', 'PENN', 'BETZ', 'REGN', 'VRTX', 'MRK', 'UNH', 'TMO', 'ISRG', 'ABT', 'IDXX', 'TDOC', 'CRSP', 
    'BRK-B', 'ETN', 'CAT', 'BLD', 'U', 'RBLX', 'SKLZ', 'FSLY', 'TRIP', 'EXPE', 'BKNG', 'ABNB', 'DIS', 'WMT', 
    'COST', 'TGT', 'LOW', 'HD', 'DT', 'SNPS', 'CDNS', 'MDB', 'ORCL', 'NOW', 'ADP', 'SNOW', 'DDOG', 
    'FROG', 'ADSK', 'INTU', 'TEAM', 'WDAY', 'CRM', 'PAYC', 'ANET', 'ADBE', 'ACN', 'EPAM', 'ZM', 'TTD', 'TWLO', 
    'DASH', 'APPS', 'DOCU', 'AI', 'AKAM', 'QLYS', 'PANW', 'FTNT', 'CRWD', 'TENB', 'OKTA', 'ZS', 
    'NET', 'S', 'UMC', 'ASML', 'KEYS', 'CRUS', 'AMD', 'AVGO', 'MU', 'KLAC', 'TXN', 'QRVO', 'TSM', 'SWKS', 'AMBA', 
    'STM', 'MCHP', 'ON', 'QCOM', 'SOXX', 'MRVL', 'ADI', 'LRCX', 'AMAT', 'WDC', 'NXPI', 'TER', 'MPWR', 'INTC', 
    'GFS', 'STX', 'A', 'ZBRA', 'ENTG', 'ONTO', 'TRMB', 'BNTX', 'PFE', 'MRNA', 'NVAX', 'FCX', 'CF', 'DRI', 
    'PEP', 'XOM', 'LLY', 'CL', 'MCD', 'KO', 'GE', 'CVX', 'FISV', 'DE', 'WM', 'HLT', 'FUTU', 'UBER', 
    'TIGR', 'EQIX', 'DPZ', 'CSCO', 'COKE', 'SONY', 'FDS', 'MCO', 'GRAB', 'PTON', 'AMT', 'LIT', 'CMG', 'IPO', 
    'PSTG', 'INMD', 'NNDM', 'MP', 'FUBO', 'SPOT', 'ALGN', 'PZZA', 'LOVE', 'LMND', 'POOL', 'PLTR', 'ROKU', 
    'CELH', 'NFLX', 'DHI', 'DELL'
]
# Ensure uniqueness
KNOWN_STOCKS = list(set(KNOWN_STOCKS))

LIME_STOCKS = [
    'CIBR', 'COPX', 'DRAM', 'GDX', 'IBIT', 'IGV', 'IHI',
    'IPAY', 'ITB', 'JETS', 'KRE', 'KWEB', 'LIT', 'MAGS',
    'PBW', 'REMX', 'SHLD', 'SIL', 'SLX', 'SMH', 'TAN',
    'UFO', 'URA', 'USO', 'VTV', 'VUG', 'WGMI', 'XBI',
    'XME', 'XRT', 'XTL', 'SPY', 'QQQ'
]
#'KBE', 'NLR', 'CLOU', 'XHB', 'BUG', 'HACK', 'ITA', 'IAT', 'XOP', 

# ============================================================
# SHARED DOWNLOAD: runs once, feeds all history compute fns
# ============================================================
@st.cache_data(ttl=3600)
def download_known_stocks_data(stocks_tuple):
    benchmark_symbol = "^GSPC"
    all_symbols = list(stocks_tuple) + [benchmark_symbol]
    raw_data = yf.download(all_symbols, period="2y", interval="1d", progress=False, auto_adjust=True)

    ticker_dfs = {}
    for ticker in stocks_tuple:
        try:
            df = pd.DataFrame({
                'Open':   raw_data['Open'][ticker],
                'High':   raw_data['High'][ticker],
                'Low':    raw_data['Low'][ticker],
                'Close':  raw_data['Close'][ticker],
                'Volume': raw_data['Volume'][ticker]
            }).dropna()
            if not df.empty:
                ticker_dfs[ticker] = df
        except Exception:
            continue

    benchmark_df = pd.DataFrame({
        'Close': raw_data['Close'][benchmark_symbol]
    }).dropna()

    return ticker_dfs, benchmark_df

@st.cache_data(ttl=3600)
def download_lime_stocks_data(stocks_tuple):
    raw_data = yf.download(list(stocks_tuple), period="2mo", interval="1d", progress=False, auto_adjust=True)
    ticker_dfs = {}
    for ticker in stocks_tuple:
        try:
            df = pd.DataFrame({
                'Open':   raw_data['Open'][ticker],
                'High':   raw_data['High'][ticker],
                'Low':    raw_data['Low'][ticker],
                'Close':  raw_data['Close'][ticker],
                'Volume': raw_data['Volume'][ticker]
            }).dropna()
            if not df.empty:
                ticker_dfs[ticker] = df
        except Exception:
            continue
    return ticker_dfs

# ==============================================================================
# MARKET BREADTH & STAGE ANALYSIS FOR KNOWN_STOCKS
# (Place this block ABOVE the Timing Summary section, after the Gapper section)
# ==============================================================================

@st.cache_data(ttl=3600)
def compute_breadth_and_stage(stocks_list, ticker_dfs, benchmark_df_input):
    """
    Computes IBD-style market breadth stats and stage analysis
    for the given stock list, mirroring the original Python screener logic.
    """
    try:
        breadth_stats = {
            'new_high': 0, 'new_low': 0,
            'advance': 0, 'decline': 0,
            'up_from_open': 0, 'down_from_open': 0,
            'up_volume': 0, 'down_volume': 0,
            'up_4pct': 0, 'down_4pct': 0
        }
        new_high_tickers = []  # ADD THIS
        stage_counts = {1: 0, 2: 0, 3: 0, 4: 0, 0: 0}
        total_processed = 0

        for ticker in stocks_list:
            try:
                df = ticker_dfs.get(ticker)
                if df is None or len(df) < 5:
                    continue

                currentClose = df['Close'].iloc[-1]
                prevClose    = df['Close'].iloc[-2]
                currentOpen  = df['Open'].iloc[-1]
                currentVol   = df['Volume'].iloc[-1]
                prevVol      = df['Volume'].iloc[-2]

                # 52-week high/low (exclude today for high, mirror original logic)
                low_of_52week  = float(df['Low'].values[-261:-1].min()) if len(df) >= 261 else float(df['Low'].values[:-1].min())
                high_of_52week = float(df['High'].values[-260:-1].max()) if len(df) >= 260 else float(df['High'].values[:-1].max())

                pct_change = (currentClose - prevClose) / prevClose if prevClose != 0 else 0

                total_processed += 1

                # 1. New High / New Low
                if currentClose >= high_of_52week:
                    breadth_stats['new_high'] += 1
                    new_high_tickers.append(ticker)  # ADD THIS
                if currentClose <= low_of_52week:
                    breadth_stats['new_low'] += 1

                # 2. Advance / Decline
                if currentClose > prevClose:
                    breadth_stats['advance'] += 1
                elif currentClose < prevClose:
                    breadth_stats['decline'] += 1

                # 3. Up from Open / Down from Open
                if currentClose > currentOpen:
                    breadth_stats['up_from_open'] += 1
                elif currentClose < currentOpen:
                    breadth_stats['down_from_open'] += 1

                # 4. Up on Volume / Down on Volume
                if currentClose > prevClose and currentVol > prevVol:
                    breadth_stats['up_volume'] += 1
                elif currentClose < prevClose and currentVol > prevVol:
                    breadth_stats['down_volume'] += 1

                # 5. Up 4% / Down 4%
                if pct_change >= 0.04:
                    breadth_stats['up_4pct'] += 1
                elif pct_change <= -0.04:
                    breadth_stats['down_4pct'] += 1

                # ── Stage Analysis ──────────────────────────────────────────────
                # Requires benchmark alignment and at least 260 bars
                if len(df) < 260 or benchmark_df_input is None or benchmark_df_input.empty:
                    stage_counts[0] += 1
                    continue

                df_idx = df.index.tz_localize(None) if df.index.tz is not None else df.index
                bm_idx = benchmark_df_input.index.tz_localize(None) if benchmark_df_input.index.tz is not None else benchmark_df_input.index

                df_aligned = df.copy()
                df_aligned.index = df_idx
                bm_aligned = benchmark_df_input.copy()
                bm_aligned.index = bm_idx

                combined = pd.merge(
                    df_aligned[['Close', 'Open']],
                    bm_aligned[['Close']].rename(columns={'Close': 'Close_bench'}),
                    left_index=True, right_index=True, how='inner'
                )

                if combined.empty:
                    stage_counts[0] += 1
                    continue

                # EMA 126 of stock close (for price vs trend line check)
                ema126 = df_aligned['Close'].ewm(span=126, adjust=False).mean()

                # RS Ratio
                rs = combined['Close'] / combined['Close_bench']

                # 8 EMAs of RS ratio (matches original screener)
                ema_spans = [21, 42, 63, 72, 84, 126, 147, 168]
                rs_emas = {span: rs.ewm(span=span, adjust=False).mean() for span in ema_spans}

                last = combined.index[-1]
                rsme  = rs.loc[last]
                c     = combined['Close'].loc[last]
                o     = combined['Open'].loc[last]

                # Align ema126 to combined index
                ema126_val = ema126.reindex(combined.index, method='ffill').loc[last]

                r21  = rs_emas[21].loc[last]
                r42  = rs_emas[42].loc[last]
                r63  = rs_emas[63].loc[last]
                r72  = rs_emas[72].loc[last]
                r84  = rs_emas[84].loc[last]
                r126 = rs_emas[126].loc[last]
                r147 = rs_emas[147].loc[last]
                r168 = rs_emas[168].loc[last]

                # Stage logic (exact mirror of original screener, checked in order)
                if rsme >= r84 and rsme < r126:
                    stage = 1
                elif (rsme < r42 and rsme >= r72 and rsme >= r84 and rsme >= r126
                      and (r42 > r63 or rsme < r63) and r63 > r126 and c >= ema126_val):
                    stage = 3
                elif (rsme >= r168 and rsme >= r147 and rsme >= r126
                      and c >= ema126_val and (r21 >= r42 or r42 >= r63)):
                    stage = 2
                elif rsme >= r126 and c >= ema126_val and (r21 >= r42 or r42 >= r63):
                    stage = 2
                elif (rsme < r63 and rsme < r126) or (r63 < r126 and rsme < r126):
                    stage = 4
                elif (o >= ema126_val or c >= ema126_val) and rsme >= r72 and rsme < r126:
                    stage = 1
                elif rsme >= r84 and rsme >= r72 and (o >= ema126_val or c >= ema126_val):
                    stage = 1
                else:
                    stage = 0

                stage_counts[stage] += 1

            except Exception:
                stage_counts[0] += 1
                continue

        return breadth_stats, stage_counts, total_processed, new_high_tickers

    except Exception as e:
        return {}, {1: 0, 2: 0, 3: 0, 4: 0, 0: 0}, 0

# 3. Sidebar Inputs
with st.sidebar:
    st.header("Settings")
    benchmark = "^GSPC" #benchmark = st.selectbox("Benchmark", ["^GSPC", "^IXIC"], index=0)
    rs_length = st.number_input("RS Lookback Length", value=90, min_value=10)
    top_n = st.number_input("Top N for Group Avg", value=5, min_value=1)
    show_all_rs = st.toggle("Show RS < 80", value=False)
    show_ppp_charts = st.toggle("Show PPP Charts", value=False)
    show_gap_charts = st.toggle("Show Gap Charts", value=False)
    show_all_setups = st.toggle("Show All Setups (top-5)", value=True)
    
    if st.button("Refresh Deepvue Theme", use_container_width=True):
        # Clear the caches for BOTH functions so fresh data is requested
        download_lime_stocks_data.clear()
        st.toast("Cache cleared! Fetching real-time market data...", icon="🔄")

    if st.button("Refresh Deepvue Breadth", use_container_width=True):
        # Clear the caches for BOTH functions so fresh data is requested
        compute_breadth_and_stage.clear()
        st.toast("Cache cleared! Fetching real-time market data...", icon="🔄")

    if st.button("Clear Cache & Refresh"):
        st.cache_data.clear()

# st.markdown("---")
#st.markdown(f"#### 📊 Market Breadth")

lime_ticker_dfs = download_lime_stocks_data(tuple(LIME_STOCKS))

lime_perf_rows = []
for sym in LIME_STOCKS:
    df_sym = lime_ticker_dfs.get(sym)
    if df_sym is None or len(df_sym) < 2:
        continue
    c_today = df_sym['Close'].iloc[-1]
    c_prev  = df_sym['Close'].iloc[-2]
    if pd.isna(c_today) or pd.isna(c_prev) or c_prev == 0:
        continue
    pct_1d = round((c_today - c_prev) / c_prev * 100, 2)

    c_1w = df_sym['Close'].iloc[-6] if len(df_sym) >= 6 else None
    pct_1w = round((c_today - c_1w) / c_1w * 100, 2) if (c_1w is not None and not pd.isna(c_1w) and c_1w != 0) else None

    c_1m = df_sym['Close'].iloc[-22] if len(df_sym) >= 22 else None
    pct_1m = round((c_today - c_1m) / c_1m * 100, 2) if (c_1m is not None and not pd.isna(c_1m) and c_1m != 0) else None

    lime_perf_rows.append({"sym": sym, "pct": pct_1d, "pct_1w": pct_1w, "pct_1m": pct_1m})

if lime_perf_rows:
    BAR_MAX_PX = 175  # was 200

    rows_1d = sorted(lime_perf_rows, key=lambda x: -x["pct"])
    rows_1w = sorted([r for r in lime_perf_rows if r["pct_1w"] is not None], key=lambda x: -x["pct_1w"])
    rows_1m = sorted([r for r in lime_perf_rows if r["pct_1m"] is not None], key=lambda x: -x["pct_1m"])

    max_abs_1d = max(abs(r["pct"])     for r in rows_1d) or 1
    max_abs_1w = max(abs(r["pct_1w"])  for r in rows_1w) or 1
    max_abs_1m = max(abs(r["pct_1m"])  for r in rows_1m) or 1

    ROW_H   = 22   # was 18
    LABEL_W = 126   # was 110
    COL_W   = LABEL_W + BAR_MAX_PX
    GAP     = 60   # was 60
    PADDING = 14    # was 12
    FS      = 14    # font size

    N      = max(len(rows_1d), len(rows_1w), len(rows_1m))
    SVG_H  = N * ROW_H + PADDING * 2
    SVG_W  = COL_W * 3 + GAP * 2 + PADDING * 2

    X0_1d = PADDING
    X0_1w = PADDING + COL_W + GAP
    X0_1m = PADDING + (COL_W + GAP) * 2

    HEADER_H = 20  # height reserved for header row
    SVG_H    = N * ROW_H + PADDING * 2 + HEADER_H  # add header height to SVG

    def col_header(col_x, label):
        center_x = col_x + LABEL_W // 2 + BAR_MAX_PX // 2
        return (
            f'<text x="{center_x}" y="{PADDING + 12}" '
            f'font-size="10" font-family="Source Sans Pro,sans-serif" '
            f'font-weight="700" fill="#888888" text-anchor="middle" '
            f'letter-spacing="1">{label}</text>'
        )

    headers_html = (
        col_header(X0_1d, "DAILY") +
        col_header(X0_1w, "1 WEEK") +
        col_header(X0_1m, "1 MONTH")
    )

    def row_y(i):
        return PADDING + HEADER_H + i * ROW_H + ROW_H

    def bar_end_x(col_x, pct, max_abs):
        return col_x + LABEL_W + int(abs(pct) / max_abs * BAR_MAX_PX)

    def color(pct):
        return "#378ADD" if pct >= 0 else "#FF69B4"

    def sign(pct):
        return f"+{pct:.2f}%" if pct >= 0 else f"{pct:.2f}%"

    def build_index(rows, pct_key, max_abs, col_x):
        return {
            r["sym"]: (i, bar_end_x(col_x, r[pct_key], max_abs))
            for i, r in enumerate(rows)
        }

    idx_1d = build_index(rows_1d, "pct",    max_abs_1d, X0_1d)
    idx_1w = build_index(rows_1w, "pct_1w", max_abs_1w, X0_1w)
    idx_1m = build_index(rows_1m, "pct_1m", max_abs_1m, X0_1m)

    lines_html = ""

    for sym, (i_1d, ex_1d) in idx_1d.items():
        if sym not in idx_1w:
            continue
        i_1w, ex_1w = idx_1w[sym]
        y1 = row_y(i_1d); y2 = row_y(i_1w)
        c  = color(rows_1d[i_1d]["pct"])
        lines_html += (
            f'<line class="mesh mesh-{sym}" '
            f'x1="{ex_1d}" y1="{y1}" x2="{ex_1w}" y2="{y2}" '
            f'stroke="{c}" stroke-width="1.2" stroke-opacity="0" '
            f'style="transition:stroke-opacity 0.2s;pointer-events:none;"/>'
        )

    for sym, (i_1w, ex_1w) in idx_1w.items():
        if sym not in idx_1m:
            continue
        i_1m, ex_1m = idx_1m[sym]
        y1 = row_y(i_1w); y2 = row_y(i_1m)
        c  = color(rows_1w[i_1w]["pct_1w"])
        lines_html += (
            f'<line class="mesh mesh-{sym}" '
            f'x1="{ex_1w}" y1="{y1}" x2="{ex_1m}" y2="{y2}" '
            f'stroke="{c}" stroke-width="1.2" stroke-opacity="0" '
            f'style="transition:stroke-opacity 0.2s;pointer-events:none;"/>'
        )

    def draw_col(rows, pct_key, max_abs, col_x):
        html = ""
        for i, r in enumerate(rows):
            pct   = r[pct_key]
            sym   = r["sym"]
            bw    = max(int(abs(pct) / max_abs * BAR_MAX_PX), 2)
            c     = color(pct)
            y     = row_y(i)
            label = sign(pct)
            html += (
                f'<rect class="hitbar" data-sym="{sym}" '
                f'x="{col_x}" y="{y - 7}" '
                f'width="{LABEL_W + bw}" height="19" '  # between 14 and 16
                f'fill="transparent" style="cursor:pointer;"/>'
            )
            # bar rect height 9 (between 8 and 10):
            html += (
                f'<rect class="bar bar-{sym}" data-sym="{sym}" '
                f'x="{col_x + LABEL_W}" y="{y - 4}" '
                f'width="{bw}" height="11" rx="2" fill="{c}" '
                f'style="cursor:pointer;"/>'
            )
            # label x positions scaled to new LABEL_W=100:
            html += (
                f'<text class="lbl lbl-{sym}" data-sym="{sym}" '
                f'x="{col_x + 58}" y="{y + 4}" '  # ~52% of LABEL_W
                f'font-size="{FS}" font-family="Source Sans Pro,sans-serif" '
                f'font-weight="600" fill="{c}" '
                f'text-anchor="end" style="cursor:pointer;">{label}</text>'
            )
            ticker_color = "#FFD700" if sym == "SPY" else "#ADFF2F" if sym == "QQQ" else "#cccccc"
            html += (
                f'<text class="lbl lbl-{sym}" data-sym="{sym}" '
                f'x="{col_x + 62}" y="{y + 4}" '  # 4px gap after %
                f'font-size="{FS}" font-family="Source Sans Pro,sans-serif" '
                f'font-weight="600" fill="{ticker_color}" '
                f'text-anchor="start" style="cursor:pointer;">{sym}</text>'
            )
        return html

    cols_html  = draw_col(rows_1d, "pct",    max_abs_1d, X0_1d)
    cols_html += draw_col(rows_1w, "pct_1w", max_abs_1w, X0_1w)
    cols_html += draw_col(rows_1m, "pct_1m", max_abs_1m, X0_1m)

    js = """
    <script>
    (function() {
      let selected = null;

      function reset() {
        document.querySelectorAll('.mesh').forEach(function(el) {
          el.style.strokeOpacity = '0';
        });
        document.querySelectorAll('.bar, .lbl').forEach(function(el) {
          el.style.opacity = '1';
        });
        selected = null;
      }

      function select(sym) {
        document.querySelectorAll('.bar, .lbl').forEach(function(el) {
          el.style.opacity = '0.15';
        });
        document.querySelectorAll('.mesh').forEach(function(el) {
          el.style.strokeOpacity = '0';
        });
        document.querySelectorAll('.bar-' + sym + ', .lbl-' + sym).forEach(function(el) {
          el.style.opacity = '1';
        });
        document.querySelectorAll('.mesh-' + sym).forEach(function(el) {
          el.style.strokeOpacity = '0.9';
        });
        selected = sym;
      }

      document.addEventListener('click', function(e) {
        var el = e.target.closest('[data-sym]');
        if (!el) { reset(); return; }
        var sym = el.getAttribute('data-sym');
        if (sym === selected) { reset(); }
        else { select(sym); }
      });
    })();
    </script>
    """

    html_out = f"""
    <div style="background:#0e1117; border-radius:6px;">
      <svg xmlns="http://www.w3.org/2000/svg"
           width="{SVG_W}" height="{SVG_H}"
           style="display:block;">
        {headers_html}
        {lines_html}
        {cols_html}
      </svg>
    </div>
    {js}
    """

    st.components.v1.html(html_out, height=SVG_H + 24, scrolling=False)
else:
    st.info("No Lime Stocks performance data available.")

st.markdown("---")

# ============================================================
# SINGLE DOWNLOAD + SPINNER: all compute fns share one fetch
# ============================================================
stocks_tuple = tuple(KNOWN_STOCKS)

# Single download — all history fns share this cached result
ticker_dfs_shared, benchmark_df_shared = timed(
    "download_known_stocks_data",
    download_known_stocks_data,
    stocks_tuple
)

# Inject benchmark so history functions can look it up by symbol
ticker_dfs_shared[benchmark] = benchmark_df_shared

# ── Compute ─────────────────────────────────────────────────────────────────
with st.spinner("Computing market breadth & stage analysis..."):
    breadth_stats, stage_counts, breadth_total, new_high_tickers = timed(
        "compute_breadth_and_stage",
        compute_breadth_and_stage,
        stocks_tuple, ticker_dfs_shared, benchmark_df_shared
    )

if breadth_total > 0:

    # ── Helper: one breadth bar (compact, label above, counts below) ──────
    def breadth_bar_html(title, val, counterpart):
        pair_total = val + counterpart
        if pair_total == 0:
            pct_val, pct_counter = 0, 0
        else:
            pct_val     = (val / pair_total) * 100
            pct_counter = 100 - pct_val

        is_bullish  = pct_val >= 50
        bull_color  = "#378ADD" if is_bullish else "#FF69B4"
        bear_color  = "#a9a9a9"
        pct_display = f"{pct_val:.1f}%"

        # Bar segments
        if pct_val == 0:
            bar_segs = f"<div style='width:100%;background:{bear_color};height:100%;border-radius:999px;'></div>"
        elif pct_counter == 0:
            bar_segs = f"<div style='width:100%;background:{bull_color};height:100%;border-radius:999px;'></div>"
        else:
            bar_segs = (
                f"<div style='width:{pct_val:.2f}%;background:{bull_color};height:100%;border-radius:999px 0 0 999px;'></div>"
                f"<div style='width:{pct_counter:.2f}%;background:{bear_color};height:100%;border-radius:0 999px 999px 0;'></div>"
            )

        return (
            f"<div style='margin-bottom:18px;'>"
            # Title row with pct on the right
            f"  <div style='margin-bottom:5px;font-size:14px;font-weight:700;color:#ffffff;'>"
            f"    {title} <span style='color:{bull_color};'>({pct_display})</span>"
            f"  </div>"
            # Bar — 40% width, left-aligned
            f"  <div style='width:40%;height:7px;display:flex;overflow:hidden;border-radius:999px;background:{bear_color};'>"
            f"    {bar_segs}"
            f"  </div>"
            # Counts row
            f"  <div style='display:flex;justify-content:space-between;width:40%;margin-top:4px;'>"
            f"    <span style='font-size:12px;color:#888888;'>{val:,} {title.split(' vs ')[0]}</span>"
            f"    <span style='font-size:12px;color:#888888;'>{counterpart:,} {title.split(' vs ')[1]}</span>"
            f"  </div>"
            f"</div>"
        )

    # ── Render all 5 breadth bars ─────────────────────────────────────────
    # Render New Highs bar separately with expander
    new_high_count = breadth_stats.get('new_high', 0)
    new_low_count  = breadth_stats.get('new_low', 0)
    pair_total = new_high_count + new_low_count
    pct_val     = (new_high_count / pair_total * 100) if pair_total > 0 else 0
    pct_counter = 100 - pct_val
    bull_color  = "#378ADD" if pct_val >= 50 else "#FF69B4"
    bear_color  = "#a9a9a9"

    if pct_val == 0:
        bar_segs_nh = f"<div style='width:100%;background:{bear_color};height:100%;border-radius:999px;'></div>"
    elif pct_counter == 0:
        bar_segs_nh = f"<div style='width:100%;background:{bull_color};height:100%;border-radius:999px;'></div>"
    else:
        bar_segs_nh = (
            f"<div style='width:{pct_val:.2f}%;background:{bull_color};height:100%;border-radius:999px 0 0 999px;'></div>"
            f"<div style='width:{pct_counter:.2f}%;background:{bear_color};height:100%;border-radius:0 999px 999px 0;'></div>"
        )

    st.markdown(
        f"<div style='margin-bottom:6px;font-size:14px;font-weight:700;color:#ffffff;'>"
        f"New Highs vs New Lows <span style='color:{bull_color};'>({pct_val:.1f}%)</span>"
        f"</div>"
        f"<div style='width:40%;height:7px;display:flex;overflow:hidden;border-radius:999px;background:{bear_color};margin-bottom:4px;'>"
        f"{bar_segs_nh}</div>",
        unsafe_allow_html=True
    )

    st.markdown(
        f"<div style='display:flex;justify-content:space-between;width:40%;margin-bottom:18px;'>"
        f"<span style='font-size:12px;color:#888888;'>{new_high_count:,} New Highs</span>"
        f"<span style='font-size:12px;color:#888888;'>{new_low_count:,} New Lows</span>"
        f"</div>",
        unsafe_allow_html=True
    )

    #col_nh, col_nl = st.columns([1, 9])
    #with col_nh:
    with st.expander(f""):
        if new_high_tickers:
            nh_html = (
                "<div style='display:flex;flex-wrap:wrap;gap:6px;"
                "padding:12px 4px;'>"
            )
            for sym in sorted(new_high_tickers):
                if sym in LIME_STOCKS:
                    nh_html += (
                        f'<div class="ticker-badge lime-badge">'
                        f'<span style="color:#000;font-weight:bold;">{sym}</span></div>'
                    )
                elif sym in KNOWN_STOCKS:
                    nh_html += (
                        f'<div class="ticker-badge new-pattern-badge">'
                        f'<span style="color:#111;font-weight:bold;">{sym}</span></div>'
                    )
                else:
                    nh_html += f'<div class="ticker-badge">{sym}</div>'
            nh_html += "</div>"
            st.markdown(nh_html, unsafe_allow_html=True)
        else:
            st.info("")

    # Remaining 4 breadth bars unchanged
    breadth_html = (
        breadth_bar_html('Advance vs Decline',            breadth_stats.get('advance', 0),      breadth_stats.get('decline', 0))
        + breadth_bar_html('Up from Open vs Down from Open',breadth_stats.get('up_from_open', 0), breadth_stats.get('down_from_open', 0))
        + breadth_bar_html('Up on Volume vs Down on Volume',breadth_stats.get('up_volume', 0),    breadth_stats.get('down_volume', 0))
        + breadth_bar_html('Up 4% vs Down 4%',              breadth_stats.get('up_4pct', 0),      breadth_stats.get('down_4pct', 0))
    )
    st.markdown(breadth_html, unsafe_allow_html=True)

st.markdown("---")


# 4. IMPLEMENTATION OF NEW NORMALIZED RS METHOD AND EMA CLOUD
@st.cache_data(ttl=3600)
def get_rs_and_cloud_data_cached(tickers_tuple, benchmark_ticker, length): # <-- Added length parameter
    tickers = list(tickers_tuple)
    try:
        all_tickers = tickers + [benchmark_ticker]
        # Download data (ensuring enough historical data to compute the rolling min/max lookback window)
        data = yf.download(all_tickers, period="2y", interval="1d", progress=False, auto_adjust=True)
        
        close_data = data['Close']
        high_data = data['High']
        low_data = data['Low']
        open_data = data['Open']

        # Drop the latest bar if it is mostly NaN — this is the unsettled intraday row
        # yf.download with auto_adjust=False sometimes appends it; download_known_stocks_data
        # avoids it via per-ticker .dropna(), so we align here to prevent NaN RS scores
        global _latest_bar_dropped
        latest_row_nan_pct = close_data.iloc[-1].isna().mean()
        if latest_row_nan_pct > 0.3:
            close_data = close_data.iloc[:-1]
            high_data  = high_data.iloc[:-1]
            low_data   = low_data.iloc[:-1]
            open_data  = open_data.iloc[:-1]
            _latest_bar_dropped = True
        else:
            _latest_bar_dropped = False
        
        valid_tickers = [t for t in tickers if t in close_data.columns and close_data[t].notna().sum() >= length]
        if not valid_tickers: return None, None, None, {}, None, None, None, None, None

        # --- New RS Logic ---
        bench_close = close_data[benchmark_ticker]
        stock_scores = {}
        stock_scores_prev = {}
        stock_scores_1m = {}
        cloud_tickers = []
        cloud_21ema_tickers = []
        cloud_wick_tickers = []
        ma50_bounce_tickers = []
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
            
            #if ema_low <= current_price <= ema_high:
            #    cloud_tickers.append(ticker)

            # ================================
            # BUYABLE-STYLE 21 EMA CLOUD LOGIC
            # ================================

            ema21_close = close_data[ticker].ewm(span=21, adjust=False).mean().iloc[-1]
            ema21_low   = low_data[ticker].ewm(span=21, adjust=False).mean().iloc[-1]

            sma50_series = close_data[ticker].rolling(50).mean()
            sma50 = sma50_series.iloc[-1]
            sma50_prev1 = sma50_series.iloc[-2] if len(sma50_series) > 2 else sma50
            sma50_prev2 = sma50_series.iloc[-3] if len(sma50_series) > 3 else sma50

            # --- MA50 Rising ---
            ma50Rising = (sma50 > sma50_prev1) and (sma50_prev1 > sma50_prev2)

            # --- EMA50 gradient ---
            powerma = close_data[ticker].ewm(span=50, adjust=False).mean()
            gradient = (powerma.iloc[-1] - powerma.iloc[-2]) if len(powerma) > 1 else 0

            # --- ATR% ---
            high = high_data[ticker]
            low = low_data[ticker]
            close = close_data[ticker]

            tr = pd.concat([
                high - low,
                abs(high - close.shift(1)),
                abs(low - close.shift(1))
            ], axis=1).max(axis=1)

            atr = tr.rolling(14).mean()
            atrPercent = (atr / close) * 100

            atr21_R = (((close.iloc[-1] - ema21_close) / close.iloc[-1]) * 100) / (atrPercent.iloc[-1] + 1e-6)
            atr50_R = (((close.iloc[-1] - sma50) / close.iloc[-1]) * 100) / (atrPercent.iloc[-1] + 1e-6)

            # --- EMA distance filter ---
            emaDistPercent = ((close.iloc[-1] - ema21_low) / close.iloc[-1]) * 100

            # --- BUYABLE CONDITIONS ---
            hl_ratio = high_data[ticker] / low_data[ticker]
            adr_sma = hl_ratio.rolling(20).mean()

            adrPercent = 100 * (adr_sma - 1)

            cond1 = (adrPercent.iloc[-1] >= 2.45) and (adrPercent.iloc[-1] <= 8)

            cond2 = -0.5 <= atr21_R <= 1
            cond3 = 0 <= atr50_R <= 3
            cond4 = 0 < emaDistPercent <= 8
            cond5 = close.iloc[-1] > ema21_low

            # --- smoothing logic placeholders (simplified version) ---
            pbb_cond1 = True
            pbb_cond2 = gradient >= 0
            pbb_cond3 = True

            is_pine_7_valid = False
            if len(close_data) >= 260:
                # 1. Moving Averages
                sma150_series = close_data[ticker].rolling(window=150).mean()
                sma200_series = close_data[ticker].rolling(window=200).mean()
                
                c_sma150 = sma150_series.iloc[-1]
                c_sma200 = sma200_series.iloc[-1]
                c_sma200_22 = sma200_series.iloc[-23] if len(sma200_series) >= 23 else c_sma200
                
                # 2. 52-Week (260 Days) Lookback Highs and Lows
                c_highest = high_data[ticker].rolling(window=260).max().iloc[-1]
                c_lowest = low_data[ticker].rolling(window=260).min().iloc[-1]
                
                # 3. Calculate 7 Flag Criteria
                c1 = 1 if (close.iloc[-1] > c_sma150 and close.iloc[-1] > c_sma200) else 0
                c2 = 1 if (c_sma150 > c_sma200) else 0
                c3 = 1 if (c_sma200 > c_sma200_22) else 0
                c4 = 1 if (sma50 > c_sma150 and sma50 > c_sma200) else 0
                c5 = 1 if (close.iloc[-1] > sma50) else 0
                c6 = 1 if (((close.iloc[-1] / c_lowest) - 1) * 100 >= 25) else 0
                c7 = 1 if ((1 - (close.iloc[-1] / c_highest)) * 100 <= 25) else 0
                
                pine_count = c1 + c2 + c3 + c4 + c5 + c6 + c7
                is_pine_7_valid = (pine_count == 7)

            # --- FINAL BUYABLE FILTER ---
            buyable = (
                cond1 and
                cond2 and
                cond3 and
                cond4 and
                pbb_cond2 and
                (pbb_cond1 or pbb_cond3) and
                ma50Rising and
                close.iloc[-1] >= 20 and 
                is_pine_7_valid
            )

            if ticker == "AMD" and _latest_bar_dropped:
                st.sidebar.warning("⚠️ DEBUGGING FOR AMD ACTIVATED")
                
                # Check metrics availability
                debug_info = {
                    "Ticker Symbol": ticker,
                    "Current Cached Price": round(current_price, 2) if 'current_price' in locals() else "N/A",
                    "Total Raw RS Score": total_score,
                    "Has Data Available": ticker in close_data.columns,
                    "Historical Bars Fetched": int(close_data[ticker].notna().sum()),
                    "Requested Window Length": length,
                    "Is Current High NaN": pd.isna(current_hh),
                    "Is Current Low NaN": pd.isna(current_ll)
                }
                st.sidebar.json(debug_info)            

            # ================================
            # DEBUG AMAT
            # ================================
            # if ticker == "AMAT":
            #     debug_data = {"ticker": ticker,"close": round(close.iloc[-1], 2),"adrPercent": round(float(adrPercent.iloc[-1]), 2),"cond1_adr_2.45_to_8": cond1,"atr21_R": round(float(atr21_R), 2),"cond2_atr21": cond2,"atr50_R": round(float(atr50_R), 2),"cond3_atr50": cond3,"emaDistPercent": round(float(emaDistPercent), 2),"cond4_emaDist": cond4,"gradient": round(float(gradient), 4),"pbb_cond2_gradient_positive": pbb_cond2,"sma50": round(float(sma50), 2),"sma50_prev1": round(float(sma50_prev1), 2),"sma50_prev2": round(float(sma50_prev2), 2),"ma50Rising": ma50Rising,"close_gt_20": close.iloc[-1] >= 20,"FINAL_BUYABLE": buyable}
            #     st.write(debug_data)

            # ================================
            # CLOUD CONDITION (UPDATED)
            # ================================
            if buyable:
                cloud_tickers.append(ticker)

            # ================================
            # 21 EMA CLOUD CONDITION (finalCondition)
            # ================================
            if len(close_data[ticker]) >= 3 and len(low_data[ticker]) >= 3 and len(high_data[ticker]) >= 3 and len(open_data[ticker]) >= 3:
                ema21_low_series  = low_data[ticker].ewm(span=21, adjust=False).mean()
                ema21_high_series = high_data[ticker].ewm(span=21, adjust=False).mean()

                MALow0  = ema21_low_series.iloc[-1]
                MALow1  = ema21_low_series.iloc[-2]
                MALow2  = ema21_low_series.iloc[-3]
                MAHigh0 = ema21_high_series.iloc[-1]
                MAHigh1 = ema21_high_series.iloc[-2]
                MAHigh2 = ema21_high_series.iloc[-3]

                c0 = close_data[ticker].iloc[-1]
                c1 = close_data[ticker].iloc[-2]
                c2 = close_data[ticker].iloc[-3]
                o0 = open_data[ticker].iloc[-1]
                o1 = open_data[ticker].iloc[-2]
                o2 = open_data[ticker].iloc[-3]
                h0 = high_data[ticker].iloc[-1]
                h1 = high_data[ticker].iloc[-2]
                h2 = high_data[ticker].iloc[-3]
                l0 = low_data[ticker].iloc[-1]
                l1 = low_data[ticker].iloc[-2]
                l2 = low_data[ticker].iloc[-3]

                insideCloud0 = MALow0 <= c0 <= MAHigh0
                insideCloud1 = MALow1 <= c1 <= MAHigh1
                insideCloud2 = MALow2 <= c2 <= MAHigh2

                insideCloud3Days         = insideCloud0 and insideCloud1 and insideCloud2
                insideCloud2DaysPositive = insideCloud0 and insideCloud1 and (c0 > c1) and (c0 > o0)

                bodyTop0    = max(o0, c0);  bodyBottom0 = min(o0, c0);  bodySize0 = bodyTop0 - bodyBottom0
                bodyTop1    = max(o1, c1);  bodyBottom1 = min(o1, c1);  bodySize1 = bodyTop1 - bodyBottom1
                bodyTop2    = max(o2, c2);  bodyBottom2 = min(o2, c2);  bodySize2 = bodyTop2 - bodyBottom2

                insideBody0 = max(0.0, min(bodyTop0, MAHigh0) - max(bodyBottom0, MALow0))
                insideBody1 = max(0.0, min(bodyTop1, MAHigh1) - max(bodyBottom1, MALow1))
                insideBody2 = max(0.0, min(bodyTop2, MAHigh2) - max(bodyBottom2, MALow2))

                insidePct0 = (insideBody0 / bodySize0) if bodySize0 > 0 else 0.0
                insidePct1 = (insideBody1 / bodySize1) if bodySize1 > 0 else 0.0
                insidePct2 = (insideBody2 / bodySize2) if bodySize2 > 0 else 0.0

                bodyCloud3Days = insidePct0 >= 0.70 and insidePct1 >= 0.70 and insidePct2 >= 0.70
                finalCondition = bodyCloud3Days or insideCloud3Days or insideCloud2DaysPositive

                if buyable and finalCondition and close_data[ticker].iloc[-1] >= 20:
                    cloud_21ema_tickers.append(ticker)

            # ================================
            # 21 EMA WICK CONDITION (longWickToday)
            # ================================
            h_today = high_data[ticker].iloc[-1]
            l_today = low_data[ticker].iloc[-1]
            o_today = open_data[ticker].iloc[-1]
            c_today = close_data[ticker].iloc[-1]

            rangeToday     = h_today - l_today
            lowerWickToday = min(o_today, c_today) - l_today
            longWickToday  = (lowerWickToday / rangeToday) > 0.5 if rangeToday > 0 else False

            if buyable and longWickToday and c_today >= 20:
                cloud_wick_tickers.append(ticker)

            # ================================
            # 50MA BOUNCE CONDITION (ma50_bounce_cond)
            # ================================
            sma50_series_full = close_data[ticker].rolling(50).mean()
            if len(sma50_series_full) >= 2 and len(low_data[ticker]) >= 2:
                sma50_today = sma50_series_full.iloc[-1]
                sma50_yest  = sma50_series_full.iloc[-2]
 
                if pd.isna(sma50_today) or pd.isna(sma50_yest) or sma50_today == 0:
                    pass
                else:
                    fiftyday_percent  = (close_data[ticker].iloc[-1] - sma50_today) / sma50_today * 100
                    # truncate to 1 decimal place (mirrors Pine Script truncate())
                    fiftyday_percent2 = int(fiftyday_percent * 10) / 10
 
                    touchMA50_yest = low_data[ticker].iloc[-2] <= sma50_yest
                    recover1       = touchMA50_yest and (close_data[ticker].iloc[-1] > sma50_today)
 
                    ma50_bounce_cond = (
                        recover1 and
                        cond1 and
                        fiftyday_percent2 <= 8 and
                        ma50Rising and
                        close_data[ticker].iloc[-1] >= 20 and 
                        is_pine_7_valid
                    )
 
                    if ma50_bounce_cond:
                        ma50_bounce_tickers.append(ticker)

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
        
        return rs_perf, rs_perf, cloud_tickers, price_lookup, rs_perf_prev, rs_perf_1m, cloud_21ema_tickers, cloud_wick_tickers, ma50_bounce_tickers
    except Exception as e:
        st.error(f"Error: {e}")
        return None, None, None, {}, None, None, None, None, None

# Reference Scanner Logic Functions
# def scan_two_botak(df, lookback=0):
#     idx = -1 - lookback
#     if len(df) < abs(idx) + 1: return False
#     botak = (
#         (abs(df['Close'] - df['High']) < 0.05) & 
#         (df['Close'] > df['Open'])
#     )
#     percentile = (
#         (df['Close'] > df['Open']) & 
#         (((df['Close'] - df['Open']) / ((df['High'] - df['Open']).replace(0, 0.001))) > 0.9)
#     )
#     twoBotak = (
#         ((botak & botak.shift(1)) |
#         (botak & percentile.shift(1)) |
#         (percentile & botak.shift(1)) |
#         (percentile & percentile.shift(1))) &
#         (df['Close'] > 20)
#     )
#     return bool(twoBotak.iloc[idx])

# def scan_gapper(df, lookback=0):
#     idx = -1 - lookback
#     if len(df) < 22 + lookback: return False

#     df = df.copy().reset_index(drop=True)  # guarantee clean integer index

#     strictGapUp = df['Low'] > df['High'].shift(1)
#     gapPercent  = (df['Close'] / df['Close'].shift(1)) - 1
#     gapUp10     = strictGapUp & (gapPercent >= 0.10)

#     bars_since        = pd.Series(np.inf,  index=df.index)
#     gap_floor         = pd.Series(np.nan,  index=df.index)
#     gap_ceiling       = pd.Series(np.nan,  index=df.index)
#     min_low_since_gap = pd.Series(np.nan,  index=df.index)

#     counter         = np.inf
#     last_floor      = np.nan
#     last_ceiling    = np.nan
#     running_min_low = np.nan

#     for i in range(1, len(df)):   # start at 1 — need i-1 to always be valid
#         if gapUp10.iloc[i]:
#             counter         = 0
#             last_floor      = df['High'].iloc[i - 1]   # top of pre-gap candle = gap bottom
#             last_ceiling    = df['Low'].iloc[i]         # bottom of gap candle  = gap top
#             running_min_low = df['Low'].iloc[i]
#         else:
#             counter += 1
#             if not np.isnan(running_min_low):
#                 running_min_low = min(running_min_low, df['Low'].iloc[i])
                
#                 # --- THE FIX: Check if the gap was filled on this bar ---
#                 if running_min_low <= last_floor:
#                     # Gap is filled! Reset variables so it doesn't carry forward
#                     counter         = np.inf
#                     last_floor      = np.nan
#                     last_ceiling    = np.nan
#                     running_min_low = np.nan

#         bars_since.iloc[i]         = counter
#         gap_floor.iloc[i]          = last_floor
#         gap_ceiling.iloc[i]        = last_ceiling
#         min_low_since_gap.iloc[i]  = running_min_low

#     gapIn20 = bars_since <= 20

#     # Gap is unfilled only if the lowest low since gap never touched the gap floor
#     # Use gap_ceiling as an extra sanity check: floor must be below ceiling
#     validGap       = gap_floor < gap_ceiling
#     strictUnfilled = min_low_since_gap > gap_floor

#     result = gapIn20 & strictUnfilled & validGap & (df['Close'] >= 20)

#     # remap idx back since we reset_index
#     mapped_idx = len(df) + idx
#     if mapped_idx < 0 or mapped_idx >= len(df):
#         return False
#     return bool(result.iloc[mapped_idx])

# def scan_engulfing(df, lookback=0):
#     idx = -1 - lookback
#     if len(df) < 30 + lookback: return False, False
#     bullish_engulfing = (
#         (df['Open'] < df['Low'].shift(1)) &
#         (df['Close'] > df['High'].shift(1))
#     )
#     engulf_count_series = bullish_engulfing.rolling(window=30).sum()
    
#     # Logic for historical comparison
#     df_temp = df.iloc[:len(df)-lookback] if lookback > 0 else df
#     current_idx = df_temp.index[-1]
    
#     engulf_closes = df_temp.loc[bullish_engulfing, 'Close']
#     prior_engulfs = engulf_closes[engulf_closes.index < current_idx]

#     eng1 = prior_engulfs.iloc[-1] if len(prior_engulfs) >= 1 else 0
#     eng2 = prior_engulfs.iloc[-2] if len(prior_engulfs) >= 2 else 0
#     eng3 = prior_engulfs.iloc[-3] if len(prior_engulfs) >= 3 else 0

#     current_close = df_temp['Close'].iloc[-1]
#     current_count = engulf_count_series.iloc[idx]

#     two_engulf = (
#         (current_count >= 2) and
#         (current_close > 20) and
#         (current_close > eng1) and
#         (current_close > eng2)
#     )
#     three_engulf = (
#         (current_count >= 3) and
#         (current_close > 20) and
#         (current_close > eng1) and
#         (current_close > eng2) and
#         (current_close > eng3)
#     )
#     return bool(two_engulf), bool(three_engulf)

# def scan_powertrend(df, lookback=0):
#     idx = -1 - lookback
#     if len(df) < 52 + lookback: return False
#     powerma = df['Close'].ewm(span=50, adjust=False).mean()
#     gradient = powerma - powerma.shift(1)
#     gradientPct = ((powerma - powerma.shift(1)) / powerma.shift(1)) * 100
#     absGradient = abs(gradientPct)
#     powertrend = (
#         (gradient > 0) &
#         (absGradient >= 1.0) & 
#         (df['Close'] >= 20)
#     )
#     return bool(powertrend.iloc[idx])

# def scan_powertrend_not_extended(df, lookback=0):
#     idx = -1 - lookback
#     if len(df) < 52 + lookback: return False
#     powerma = df['Close'].ewm(span=50, adjust=False).mean()
#     gradient = powerma - powerma.shift(1)
#     gradientPct = ((powerma - powerma.shift(1)) / powerma.shift(1)) * 100
#     absGradient = abs(gradientPct)
    
#     powertrend = (
#         (gradient > 0) &
#         (absGradient >= 1.0) &
#         (df['Close'] >= 20)
#     )

#     high_low = df['High'] - df['Low']
#     high_close = abs(df['High'] - df['Close'].shift(1))
#     low_close = abs(df['Low'] - df['Close'].shift(1))
#     tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
#     absATR = tr.rolling(14).mean()
#     atrPercent = (absATR / df['Close']) * 100
#     sma50 = df['Close'].rolling(50).mean()
#     percentGainFromMA = ((df['Close'] - sma50) / sma50) * 100
#     atrMultiple2 = percentGainFromMA / atrPercent.replace(0, 0.001)
#     atrMultiple = (atrMultiple2 * 10).fillna(0).astype(int) / 10

#     result = (powertrend & (atrMultiple <= 4))
#     return bool(result.iloc[idx])

# def scan_value_trap(df, lookback=0):
#     idx = -1 - lookback
#     if len(df) < 50 + lookback: return False
    
#     high_low = df['High'] - df['Low']
#     high_close = abs(df['High'] - df['Close'].shift(1))
#     low_close = abs(df['Low'] - df['Close'].shift(1))
    
#     tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
#     absATR = tr.rolling(14).mean()
#     atrPercent = (absATR / df['Close']) * 100
    
#     sma50 = df['Close'].rolling(50).mean()
#     percentGainFromMA = ((df['Close'] - sma50) / sma50) * 100
    
#     atrMultiple2 = percentGainFromMA / atrPercent.replace(0, 0.001)
#     atrMultiple2 = atrMultiple2.replace([float('inf'), -float('inf')], pd.NA)
#     atrMultiple = ((atrMultiple2.fillna(0) * 10).astype(int) / 10)
    
#     result = ((atrMultiple < -4) & (df['Close'] >= 20))
#     return bool(result.iloc[idx])

# def scan_ppp(df, lookback=0):
#     idx = -1 - lookback
#     if len(df) < 200 + lookback: return False
#     high_low = df['High'] - df['Low']
#     high_close = abs(df['High'] - df['Close'].shift(1))
#     low_close = abs(df['Low'] - df['Close'].shift(1))
#     tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
#     myAtr = tr.rolling(14).mean()
#     myAtr3 = myAtr / df['Close'] * 100
#     dynamicSensitivity = myAtr3 * 0.2

#     day0 = (df['Open'] + df['Close']) / 2
#     day1 = day0.shift(1)
#     day2 = day0.shift(2)

#     diff0 = abs((day0 - day1) / day1.replace(0, 0.001) * 100)
#     diff1 = abs((day1 - day2) / day2.replace(0, 0.001) * 100)

#     sma50 = df['Close'].rolling(50).mean()
#     sma200 = df['Close'].rolling(200).mean()

#     ma21_and_ma50_or_ma200 = (
#         (
#             ((df['Close'] >= sma200) & (df['Close'] >= sma50))
#         ) &
#         (df['Close'] >= 20)
#     )

#     ppp = (
#         (diff0 < dynamicSensitivity) &
#         (diff1 < dynamicSensitivity) &
#         ma21_and_ma50_or_ma200
#     )
#     return bool(ppp.iloc[idx])

# def scan_leader(df, benchmark_df, lookback=0):
#     idx = -1 - lookback

#     if len(df) < 250 + lookback or len(benchmark_df) < 250 + lookback:
#         return False

#     try:
#         # =========================
#         # MATCH PINE SCRIPT LOGIC
#         # =========================

#         # RS Curve
#         rs = df['Close'] / benchmark_df['Close']

#         # RS Moving Average
#         rsMA = rs.ewm(span=21, adjust=False).mean()

#         # Historical RS High
#         histNH = rs.rolling(250).max()

#         # Current values
#         rs_now = rs.iloc[idx]
#         rsMA_now = rsMA.iloc[idx]
#         histNH_now = histNH.iloc[idx]
#         close_now = df['Close'].iloc[idx]

#         # =========================
#         # circleCond
#         # =========================
#         circleCond = rs == histNH

#         # =========================
#         # twoCircles30
#         # =========================
#         circleCount30 = circleCond.rolling(30).sum()
#         twoCircles30 = circleCount30.iloc[idx] >= 2

#         # =========================
#         # MA CONDITIONS
#         # =========================
#         sma50 = df['Close'].rolling(50).mean()
#         sma200 = df['Close'].rolling(200).mean()

#         sma50_now = sma50.iloc[idx]
#         sma200_now = sma200.iloc[idx]

#         # =========================
#         # FINAL LEADER CONDITION
#         # =========================
#         leader_cond = (
#             (twoCircles30 or rs_now == histNH_now) and
#             (rs_now > rsMA_now) and
#             (close_now > sma50_now) and
#             (close_now > sma200_now) and
#             (close_now >= 20)
#         )

#         return bool(leader_cond)

#     except:
#         return False

@st.cache_data(ttl=3600)
def process_pattern_scanners(stocks_list, ticker_dfs, benchmark_df_input):
    try:
        benchmark_symbol = "^GSPC"

        # Today's Matches
        botak_matches = []
        engulf2_matches = []
        engulf3_matches = []
        powertrend_matches = []
        powertrend_ne_matches = []
        value_trap_matches = []
        ppp_matches = []
        leader_matches = []
        leader_rs_nh_matches = []
        gapper_matches = []
        gapper_gap_levels = {}
        
        # Yesterday's Matches (for color logic)
        botak_yest = []
        engulf2_yest = []
        engulf3_yest = []
        powertrend_yest = []
        powertrend_ne_yest = []
        value_trap_yest = []
        ppp_yest = []
        leader_yest = []
        gapper_yest = []
        ath_matches = []
        ath_yest = []

        # Initialize internal metrics tracking variables
        know_total_count = 0
        know_positive_count = 0
        email_content_stocks = []  # Tracks tuples of (ticker, is_new_addition)
        email_content_removed = [] # Tracks dropped Minervini stocks compared to yesterday
        extra_52wk_high_symbols = []
        extra_52wk_high_removed = []
        ema200_above_count = 0
        ema200_total_count = 0

        benchmark_df = benchmark_df_input

        for ticker in stocks_list:
            try:
                ticker_df = ticker_dfs.get(ticker)
                if ticker_df is None or ticker_df.empty:
                    continue
                
                df_len = len(ticker_df)
                if df_len < 50:
                    continue

                # Cache Close series to reduce repeatedly accessing a string key index on DataFrame
                close_series = ticker_df['Close']
                high_series  = ticker_df['High']
                low_series   = ticker_df['Low']
                open_series  = ticker_df['Open']
                vol_series   = ticker_df['Volume']

                # ── Pre-compute shared indicator series ONCE per ticker ──────────────────
                # These are reused by multiple scan blocks below for both today and yesterday

                # EMA 200
                if df_len >= 200:
                    ema200_val = close_series.ewm(span=200, adjust=False).mean().iloc[-1]
                    ema200_total_count += 1
                    if close_series.iloc[-1] > ema200_val:
                        ema200_above_count += 1

                # SMA 50 / 150 / 200
                sma50_series  = close_series.rolling(50).mean()  if df_len >= 50  else None
                sma150_series = close_series.rolling(150).mean() if df_len >= 150 else None
                sma200_series = close_series.rolling(200).mean() if df_len >= 200 else None

                # ATR (14) — used by powertrend_ne, value_trap, scan_ppp
                if df_len >= 15:
                    high_low   = high_series - low_series
                    high_close = (high_series - close_series.shift(1)).abs()
                    low_close  = (low_series  - close_series.shift(1)).abs()
                    tr_series  = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
                    atr14      = tr_series.rolling(14).mean()
                    atr_pct    = (atr14 / close_series) * 100
                else:
                    atr14 = atr_pct = None

                # EMA 50 (PowerTrend)
                powerma = close_series.ewm(span=50, adjust=False).mean() if df_len >= 52 else None

                # RS (Leader)
                rs_series = (close_series / benchmark_df['Close']) if df_len >= 250 else None

                # ==============================================================
                # OPTIMIZED MINERVINI SCRIPTS BLOCK (TOP 1 PERFORMANCE BOOST)
                # ==============================================================
                if ticker in KNOWN_STOCKS and df_len >= 261:
                    # 1. Compute rolling averages as local temporary series (avoids costly df column allocation updates)
                    # sma50_series / sma200_series already computed above

                    # 2. Extract Today's Scalar Points (Index -1)
                    currentClose = close_series.iloc[-1]
                    prevClose    = close_series.iloc[-2]
                    Volume       = vol_series.iloc[-1]
                    moving_average_50  = sma50_series.iloc[-1]
                    moving_average_200 = sma200_series.iloc[-1]
                    moving_average_200_20 = sma200_series.iloc[-20]
                    
                    # Massively speed up 52-week min/max ranges by utilizing raw NumPy array views (.values)
                    low_of_52week  = round(ticker_df["Low"].values[-260:].min(), 2)
                    high_of_52week = round(ticker_df["High"].values[-260:-1].max(), 2)

                    # Today's Evaluation Matrix
                    cond1_t  = int(currentClose > moving_average_50 > moving_average_200)
                    cond2_t  = int(moving_average_50 > moving_average_200)
                    cond3_t  = int(moving_average_200 > moving_average_200_20)
                    cond4_t  = cond2_t  # Derived directly from cond2_t to completely eliminate a redundant boolean check
                    cond5_t  = int(currentClose > moving_average_50)
                    cond6_t  = int(currentClose >= (1.3 * low_of_52week))
                    cond7_t  = int(currentClose >= (0.75 * high_of_52week))
                    cond8_t  = int(currentClose >= 20)
                    cond9_t  = int(Volume > 20000)
                    cond10_t = int((Volume * currentClose) > 2000000)
                    
                    total_today = (cond1_t + cond2_t + cond3_t + cond4_t + cond5_t + 
                                   cond6_t + cond7_t + cond8_t + cond9_t + cond10_t)

                    # 3. Extract Yesterday's Scalar Points (Index -2)
                    yestClose  = close_series.iloc[-2]
                    yestVolume = vol_series.iloc[-2]
                    yest_ma_50       = sma50_series.iloc[-2]
                    yest_ma_200      = sma200_series.iloc[-2]
                    yest_ma_200_20   = sma200_series.iloc[-21]
                    
                    yest_low_of_52week  = round(ticker_df["Low"].values[-261:-1].min(), 2)
                    yest_high_of_52week = round(ticker_df["High"].values[-261:-2].max(), 2)

                    # Yesterday's Evaluation Matrix
                    cond1_y  = int(yestClose > yest_ma_50 > yest_ma_200)
                    cond2_y  = int(yest_ma_50 > yest_ma_200)
                    cond3_y  = int(yest_ma_200 > yest_ma_200_20)
                    cond4_y  = cond2_y
                    cond5_y  = int(yestClose > yest_ma_50)
                    cond6_y  = int(yestClose >= (1.3 * yest_low_of_52week))
                    cond7_y  = int(yestClose >= (0.75 * yest_high_of_52week))
                    cond8_y  = int(yestClose >= 20)
                    cond9_y  = int(yestVolume > 20000)
                    cond10_y = int((yestVolume * yestClose) > 2000000)

                    total_yesterday = (cond1_y + cond2_y + cond3_y + cond4_y + cond5_y + 
                                       cond6_y + cond7_y + cond8_y + cond9_y + cond10_y)
                    
                    is_at_52wk_high_today = currentClose >= high_of_52week
                    is_at_52wk_high_yest  = yestClose >= yest_high_of_52week
                    
                    qualified_today_52w = (is_at_52wk_high_today and total_today < 10)
                    was_qualified_yest  = (is_at_52wk_high_yest  and total_yesterday < 10)
                    
                    if qualified_today_52w:
                        is_new_addition_52w = not was_qualified_yest
                        extra_52wk_high_symbols.append((ticker, is_new_addition_52w))
                    elif was_qualified_yest:
                        extra_52wk_high_removed.append(ticker)

                    # Set flags
                    if total_today >= 10:
                        know_total_count += 1
                        is_new_addition    = (total_yesterday < 10)
                        is_positive_today  = (currentClose > prevClose)
                        email_content_stocks.append((ticker, is_new_addition, is_positive_today))
                        
                        if currentClose > prevClose:
                            know_positive_count += 1
                    elif total_yesterday >= 10:
                        email_content_removed.append(ticker)
                # ==============================================================

                # ── INLINE SCAN LOGIC (replaces all scan_* function calls) ───────────────
                # Each block evaluates today (idx=-1) and yesterday (idx=-2) in one pass.
                # Original scan_* functions are preserved above and unchanged.

                # --- Two Botak ---
                if df_len >= 2:
                    botak_s = (
                        (close_series - high_series).abs() < 0.05
                    ) & (close_series > open_series)
                    pct_s = (
                        (close_series > open_series) &
                        (((close_series - open_series) /
                          (high_series - open_series).replace(0, 0.001)) > 0.9)
                    )
                    two_botak_s = (
                        ((botak_s & botak_s.shift(1)) |
                         (botak_s & pct_s.shift(1))   |
                         (pct_s   & botak_s.shift(1)) |
                         (pct_s   & pct_s.shift(1)))  &
                        (close_series > 20)
                    )
                    if bool(two_botak_s.iloc[-1]): botak_matches.append(ticker)
                    if bool(two_botak_s.iloc[-2]): botak_yest.append(ticker)

                # --- All Time High Close ---
                if df_len >= 2:
                    prev_ath = close_series.shift(1).expanding().max()
                    ath_s = (
                        ~prev_ath.isna() &
                        (close_series > prev_ath) &
                        (close_series > 20)
                    )
                    if bool(ath_s.iloc[-1]): ath_matches.append(ticker)
                    if bool(ath_s.iloc[-2]): ath_yest.append(ticker)

                # --- Gapper ---
                if df_len >= 22:
                    df_g = ticker_df.copy().reset_index(drop=True)
                    strict_gap = df_g['Low'] > df_g['High'].shift(1)

                    gap_pct = (df_g['Close'] / df_g['Close'].shift(1)) - 1

                    max_gap_200 = gap_pct.shift(1).rolling(200, min_periods=1).max()

                    gapUp10 = strict_gap & (
                        (gap_pct >= 0.10) |
                        (gap_pct >= max_gap_200 * 0.99)
                    )

                    bars_since_g        = pd.Series(np.inf,  index=df_g.index)
                    gap_floor_g         = pd.Series(np.nan,  index=df_g.index)
                    gap_ceiling_g       = pd.Series(np.nan,  index=df_g.index)
                    min_low_since_gap_g = pd.Series(np.nan,  index=df_g.index)

                    ctr_g = np.inf; fl_g = np.nan; ceil_g = np.nan; run_min_g = np.nan

                    for i in range(1, len(df_g)):
                        if gapUp10.iloc[i]:
                            ctr_g     = 0
                            fl_g      = df_g['High'].iloc[i - 1]
                            ceil_g    = df_g['Low'].iloc[i]
                            run_min_g = df_g['Low'].iloc[i]
                        else:
                            ctr_g += 1
                            if not np.isnan(run_min_g):
                                run_min_g = min(run_min_g, df_g['Low'].iloc[i])
                                # --- THE FIX: Check if the gap was filled on this bar ---
                                if run_min_g <= fl_g:
                                    # Gap is filled! Reset variables so it doesn't carry forward
                                    ctr_g     = np.inf
                                    fl_g      = np.nan
                                    ceil_g    = np.nan
                                    run_min_g = np.nan
                        bars_since_g.iloc[i]         = ctr_g
                        gap_floor_g.iloc[i]          = fl_g
                        gap_ceiling_g.iloc[i]        = ceil_g
                        min_low_since_gap_g.iloc[i]  = run_min_g

                    gapIn20_g      = bars_since_g        <= 30
                    validGap_g     = gap_floor_g         <  gap_ceiling_g
                    strictUnfill_g = min_low_since_gap_g >  gap_floor_g
                    result_g       = gapIn20_g & strictUnfill_g & validGap_g & (df_g['Close'] >= 20)

                    if bool(result_g.iloc[-1]):
                        gapper_matches.append(ticker)
                        gap_bar_positions = [i for i in range(1, len(df_g)) if gapUp10.iloc[i]]
                        gap_bar_pos       = gap_bar_positions[-1]  # most recent gap bar
                        gap_bar_date      = ticker_df.index[gap_bar_pos].strftime("%Y-%m-%d")
                        gapper_gap_levels[ticker] = {
                            "floor":   round(float(fl_g),   2),
                            "ceiling": round(float(ceil_g), 2),
                            "date":    gap_bar_date,
                        }
                    if bool(result_g.iloc[-2]):  gapper_yest.append(ticker)

                # --- Bullish Engulfing (OPTIMIZED) ---
                if df_len >= 31:

                    # Only need recent bars
                    recent = ticker_df.tail(35)

                    o = recent["Open"]
                    h = recent["High"]
                    l = recent["Low"]
                    c = recent["Close"]

                    # Bullish engulfing
                    be_s = (
                        (o < l.shift(1)) &
                        (c > h.shift(1))
                    )

                    engulf_closes = c[be_s]

                    # ==========================
                    # TODAY
                    # ==========================
                    today_close = c.iloc[-1]

                    prior_today = engulf_closes.iloc[:-1] if bool(be_s.iloc[-1]) else engulf_closes

                    eng1_today = prior_today.iloc[-1] if len(prior_today) >= 1 else np.nan
                    eng2_today = prior_today.iloc[-2] if len(prior_today) >= 2 else np.nan
                    eng3_today = prior_today.iloc[-3] if len(prior_today) >= 3 else np.nan

                    cnt30_today = be_s.iloc[-30:].sum()

                    two_today = (
                        cnt30_today >= 2 and
                        today_close >= 20 and
                        pd.notna(eng1_today) and
                        pd.notna(eng2_today) and
                        today_close > eng1_today and
                        today_close > eng2_today
                    )

                    three_today = (
                        cnt30_today >= 3 and
                        today_close >= 20 and
                        pd.notna(eng1_today) and
                        pd.notna(eng2_today) and
                        pd.notna(eng3_today) and
                        today_close > eng1_today and
                        today_close > eng2_today and
                        today_close > eng3_today
                    )

                    if two_today:
                        engulf2_matches.append(ticker)

                    if three_today:
                        engulf3_matches.append(ticker)

                    # ==========================
                    # YESTERDAY
                    # ==========================
                    yest_close = c.iloc[-2]

                    engulf_yest = engulf_closes[
                        engulf_closes.index < c.index[-2]
                    ]

                    eng1_yest = engulf_yest.iloc[-1] if len(engulf_yest) >= 1 else np.nan
                    eng2_yest = engulf_yest.iloc[-2] if len(engulf_yest) >= 2 else np.nan
                    eng3_yest = engulf_yest.iloc[-3] if len(engulf_yest) >= 3 else np.nan

                    cnt30_yest = be_s.iloc[-31:-1].sum()

                    two_yest = (
                        cnt30_yest >= 2 and
                        yest_close >= 20 and
                        pd.notna(eng1_yest) and
                        pd.notna(eng2_yest) and
                        yest_close > eng1_yest and
                        yest_close > eng2_yest
                    )

                    three_yest = (
                        cnt30_yest >= 3 and
                        yest_close >= 20 and
                        pd.notna(eng1_yest) and
                        pd.notna(eng2_yest) and
                        pd.notna(eng3_yest) and
                        yest_close > eng1_yest and
                        yest_close > eng2_yest and
                        yest_close > eng3_yest
                    )

                    if two_yest:
                        engulf2_yest.append(ticker)

                    if three_yest:
                        engulf3_yest.append(ticker)

                # --- PowerTrend & PowerTrend Not Extended ---
                if powerma is not None and df_len >= 52:
                    grad_s     = powerma - powerma.shift(1)
                    grad_pct_s = (grad_s / powerma.shift(1)) * 100
                    abs_grad_s = grad_pct_s.abs()

                    pt_s = (grad_s > 0) & (abs_grad_s >= 1.0) & (close_series >= 20)

                    if bool(pt_s.iloc[-1]): powertrend_matches.append(ticker)
                    if bool(pt_s.iloc[-2]): powertrend_yest.append(ticker)

                    if atr_pct is not None and sma50_series is not None:
                        pct_gain_s  = ((close_series - sma50_series) / sma50_series) * 100
                        atr_mult2_s = pct_gain_s / atr_pct.replace(0, 0.001)
                        atr_mult_s  = (atr_mult2_s * 10).fillna(0).astype(int) / 10
                        ptne_s = pt_s & (atr_mult_s <= 4)

                        if bool(ptne_s.iloc[-1]): powertrend_ne_matches.append(ticker)
                        if bool(ptne_s.iloc[-2]): powertrend_ne_yest.append(ticker)

                # --- Value Trap ---
                if atr_pct is not None and sma50_series is not None and df_len >= 50:
                    pct_gain_vt  = ((close_series - sma50_series) / sma50_series) * 100
                    atr_mult2_vt = pct_gain_vt / atr_pct.replace(0, 0.001)
                    atr_mult2_vt = atr_mult2_vt.replace([float('inf'), -float('inf')], pd.NA)
                    atr_mult_vt  = (atr_mult2_vt.fillna(0) * 10).astype(int) / 10
                    vt_s = (atr_mult_vt < -4) & (close_series >= 20)

                    if bool(vt_s.iloc[-1]): value_trap_matches.append(ticker)
                    if bool(vt_s.iloc[-2]): value_trap_yest.append(ticker)

                # --- PPP ---
                if df_len >= 200 and sma50_series is not None and sma200_series is not None and atr_pct is not None:
                    hl_ratio_ppp = high_series / low_series
                    adr_ppp = 100 * (hl_ratio_ppp.rolling(20).mean() - 1)
                    adr_ok = (adr_ppp.iloc[-1] >= 2.45) and (adr_ppp.iloc[-1] <= 8)

                    pine7_ok = False
                    if df_len >= 260 and sma150_series is not None and sma200_series is not None:
                        c_sma150    = sma150_series.iloc[-1]
                        c_sma200    = sma200_series.iloc[-1]
                        c_sma200_22 = sma200_series.iloc[-23] if df_len >= 23 else c_sma200
                        c_highest   = high_series.rolling(260).max().iloc[-1]
                        c_lowest    = low_series.rolling(260).min().iloc[-1]
                        p2 = int(c_sma150 > c_sma200)
                        pine7_ok = (
                            int(close_series.iloc[-1] > c_sma150 and close_series.iloc[-1] > c_sma200)
                            + p2 + int(c_sma200 > c_sma200_22) + p2
                            + int(close_series.iloc[-1] > sma50_series.iloc[-1])
                            + int(((close_series.iloc[-1] / c_lowest) - 1) * 100 >= 25)
                            + int((1 - (close_series.iloc[-1] / c_highest)) * 100 <= 25)
                        ) == 7

                    if adr_ok and pine7_ok:
                        dyn_sens = atr_pct * 0.2
                        day0_s   = (open_series + close_series) / 2
                        day1_s   = day0_s.shift(1)
                        day2_s   = day0_s.shift(2)
                        diff0_s  = ((day0_s - day1_s) / day1_s.replace(0, 0.001) * 100).abs()
                        diff1_s  = ((day1_s - day2_s) / day2_s.replace(0, 0.001) * 100).abs()
                        ma_filt  = (
                            (close_series >= sma200_series) &
                            (close_series >= sma50_series)  &
                            (close_series >= 20)
                        )
                        ppp_s = (diff0_s < dyn_sens) & (diff1_s < dyn_sens) & ma_filt

                        if bool(ppp_s.iloc[-1]): ppp_matches.append(ticker)
                        if bool(ppp_s.iloc[-2]): ppp_yest.append(ticker)

                # --- Leader ---
                if rs_series is not None and df_len >= 250 and sma50_series is not None and sma200_series is not None:
                    rs_ma_s    = rs_series.ewm(span=21, adjust=False).mean()
                    hist_nh_s  = rs_series.rolling(250).max()
                    circle_s   = (rs_series == hist_nh_s)
                    cc30_s     = circle_s.rolling(30).sum()
                    two_c_s    = cc30_s >= 2

                    # Pine7 as a boolean Series
                    pine7_s = pd.Series(False, index=close_series.index)
                    if df_len >= 260 and sma150_series is not None:
                        c_sma200_22 = sma200_series.shift(22)
                        c_highest   = high_series.rolling(260).max()
                        c_lowest    = low_series.rolling(260).min()
                        pine7_s = (
                            ((close_series > sma150_series) & (close_series > sma200_series)).astype(int)
                            + (sma150_series > sma200_series).astype(int)
                            + (sma200_series > c_sma200_22).astype(int)
                            + (sma150_series > sma200_series).astype(int)
                            + (close_series > sma50_series).astype(int)
                            + (((close_series / c_lowest) - 1) * 100 >= 25).astype(int)
                            + ((1 - (close_series / c_highest)) * 100 <= 25).astype(int)
                        ) == 7

                    leader_s = (
                        (two_c_s | circle_s)         &
                        #(rs_series > rs_ma_s)         &
                        (close_series > sma50_series) &
                        (close_series > sma200_series)&
                        (close_series >= 20) &
                        (pine7_s | (rs_series > rs_ma_s))
                    )
                    if bool(leader_s.iloc[-1]): leader_matches.append(ticker)
                    if bool(leader_s.iloc[-2]): leader_yest.append(ticker)
                    if bool(leader_s.iloc[-1]):
                        if bool(circle_s.iloc[-1]):          # ADD THIS BLOCK
                            leader_rs_nh_matches.append(ticker)

                    # # ── KLAC DEBUG ──────────────────────────────────────────
                    # if ticker == "KLAC":
                    #     rs_now      = rs_series.iloc[-1]
                    #     rs_ma_now   = rs_ma_s.iloc[-1]
                    #     hist_nh_now = hist_nh_s.iloc[-1]
                    #     cc30_now    = int(cc30_s.iloc[-1])
                    #     c30_now     = bool(circle_s.iloc[-1])
                    #     two_c_now   = bool(two_c_s.iloc[-1])
                    #     c_now       = close_series.iloc[-1]
                    #     s50_now     = sma50_series.iloc[-1]
                    #     s200_now    = sma200_series.iloc[-1]

                    #     st.sidebar.markdown("---")
                    #     st.sidebar.markdown("**🔍 KLAC Leader Debug**")
                    #     st.sidebar.json({
                    #         "✅ df_len >= 250"         : df_len >= 250,
                    #         "circle (rs==250d_high)"   : c30_now,
                    #         "twoCircles30 (cc30>=2)"   : two_c_now,
                    #         "cc30 count"               : cc30_now,
                    #         "rs_now"                   : round(float(rs_now), 6),
                    #         "hist_nh_now"              : round(float(hist_nh_now), 6),
                    #         "rs > rs_ema21"            : bool(rs_now > rs_ma_now),
                    #         "rs_ema21"                 : round(float(rs_ma_now), 6),
                    #         "close > SMA50"            : bool(c_now > s50_now),
                    #         "close"                    : round(float(c_now), 2),
                    #         "sma50"                    : round(float(s50_now), 2),
                    #         "close > SMA200"           : bool(c_now > s200_now),
                    #         "sma200"                   : round(float(s200_now), 2),
                    #         "close >= 20"              : bool(c_now >= 20),
                    #         "👉 LEADER TODAY"          : bool(leader_s.iloc[-1]),
                    #     })

            except:
                continue
                
        botak_matches.sort()
        engulf2_matches.sort()
        engulf3_matches.sort()
        powertrend_matches.sort()
        powertrend_ne_matches.sort()
        value_trap_matches.sort()
        ppp_matches.sort()
        leader_matches.sort()
        gapper_matches.sort()

        know_pos_pct = (know_positive_count / know_total_count * 100) if know_total_count > 0 else 0
        pct_above_ema200 = (ema200_above_count / ema200_total_count * 100) if ema200_total_count > 0 else 0
        
        return (
            botak_matches,
            engulf2_matches,
            engulf3_matches,
            powertrend_matches,
            powertrend_ne_matches,
            value_trap_matches,
            ppp_matches,
            leader_matches,
            gapper_matches,

            botak_yest,
            engulf2_yest,
            engulf3_yest,
            powertrend_yest,
            powertrend_ne_yest,
            value_trap_yest,
            ppp_yest,
            leader_yest,
            gapper_yest,
            
            know_pos_pct,
            know_positive_count,
            know_total_count,
            email_content_stocks,
            email_content_removed,
            extra_52wk_high_symbols,
            extra_52wk_high_removed,
            pct_above_ema200,
            leader_rs_nh_matches,
            gapper_gap_levels,
            ath_matches,    # ← add
            ath_yest,       # ← add
        )
    except:
        return [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], 0, 0, 0, [], [], [], [], 0, [], [], []
    
# 5. UI Layout & Logic
#st.markdown("<h3 style='font-size: 16px; margin-bottom: 10px;'>📊 Relative Strength Screener</h3>", unsafe_allow_html=True)

all_data = []
progress_bar = st.progress(0)
status_text = st.empty()

industry_items = list(INDUSTRIES.items())
for idx, (industry_name, tickers) in enumerate(industry_items):
    status_text.text(f"Processing {industry_name}...")
    perf, rs_scores, cloud_list, price_lookup, rs_scores_prev, rs_scores_1m, cloud_21ema_list, cloud_wick_list, ma50_bounce_list = timed(
        f"RS+Cloud [{industry_name}]",
        get_rs_and_cloud_data_cached,
        tuple(tickers), benchmark, 90
    )
    
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
            "Cloud21EMA": cloud_21ema_list if cloud_21ema_list is not None else [],
            "CloudWick": cloud_wick_list if cloud_wick_list is not None else [],
            "MA50Bounce": ma50_bounce_list if ma50_bounce_list is not None else [],
            "Prices": price_lookup  # Store prices securely into dataset
        })
    
    progress_bar.progress((idx + 1) / len(industry_items))

status_text.empty()
progress_bar.empty()

global_setup_tickers = set()
global_setup_ticker_groups = {}  # ticker -> list of group RS ranks it appears in
for item in all_data:
    matched = (
        (set(item["Cloud21EMA"]) | set(item["CloudWick"]) | set(item["MA50Bounce"]))
        & set(KNOWN_STOCKS)
    )
    for sym in matched:
        global_setup_tickers.add(sym)
        if sym not in global_setup_ticker_groups:
            global_setup_ticker_groups[sym] = []
        global_setup_ticker_groups[sym].append(item["Industry"])
global_setup_count = len(global_setup_tickers)

cloud21ema_all  = set()
cloudwick_all   = set()
ma50bounce_all  = set()
for item in all_data:
    cloud21ema_all.update(item.get("Cloud21EMA", []))
    cloudwick_all.update(item.get("CloudWick",   []))
    ma50bounce_all.update(item.get("MA50Bounce",  []))

def setup_badge(sym, is_new=False, is_removed=False, extra_prefix=""):
    """Render a ticker badge, colored by setup-category precedence:
    50ma_bounce (orange) > 21ema_wick (aqua) > 21ema_cloud (purple) > new (gold) > default."""
    if is_removed:
        return f'<div class="ticker-badge removed-badge">{extra_prefix}{sym}</div>'
    if sym in ma50bounce_all:
        return (f'<div class="ticker-badge orange-badge">{extra_prefix}'
                f'<span style="color:#111111;font-weight:bold;">{sym}</span></div>')
    if sym in cloudwick_all:
        return (f'<div class="ticker-badge aqua-badge">{extra_prefix}'
                f'<span style="color:#000000;font-weight:bold;">{sym}</span></div>')
    if sym in cloud21ema_all:
        return (f'<div class="ticker-badge purple-badge">{extra_prefix}'
                f'<span style="color:#000000;font-weight:bold;">{sym}</span></div>')
    if is_new:
        return (f'<div class="ticker-badge new-pattern-badge">{extra_prefix}'
                f'<span style="color:#111111;font-weight:bold;">{sym}</span></div>')
    return f'<div class="ticker-badge">{extra_prefix}{sym}</div>'

# 6. Compact Display Logic
if all_data:
    df_main = pd.DataFrame([{"Industry": item["Industry"], "Group RS": item["Group RS"], "Group RS Prev": item["Group RS Prev"], "Group RS 1M": item["Group RS 1M"]} for item in all_data])

    # col1, col2 = st.columns([1, 1])
    # with col1:
    #     sort_by = st.selectbox("Sort by", ["Group RS (High to Low)", "Industry (A-Z)", "Group RS (Low to High)"])
    # with col2:
    #     sort_order = st.radio("Order", ["Descending", "Ascending"], horizontal=True)

    # if "Industry" in sort_by:
    #     df_main = df_main.sort_values("Industry", ascending=(sort_order == "Ascending"))
    # else:
    #     df_main = df_main.sort_values("Group RS", ascending=(sort_order == "Ascending"))

    df_main = df_main.sort_values("Group RS", ascending=False)

    # Determine structural context ranking profiles before generation iteration sequences
    df_main['Current Rank'] = range(1, len(df_main) + 1)
    
    # Sort by previous scores to resolve previous visual ranks
    #df_prev_sorted = df_main.sort_values("Group RS Prev", ascending=(sort_order == "Ascending")).copy()
    df_prev_sorted = df_main.sort_values("Group RS Prev", ascending=False).copy()
    df_prev_sorted['Prev Rank'] = range(1, len(df_prev_sorted) + 1)
    
    # Sort by 1M scores to resolve 1 month visual ranks
    #df_1m_sorted = df_main.sort_values("Group RS 1M", ascending=(sort_order == "Ascending")).copy()
    df_1m_sorted = df_main.sort_values("Group RS 1M", ascending=False).copy()
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
        background-color: #00FF00; /*FFB7C5*/
        border: 1px solid #009900; /*FF0000*/
        color: #000000;
        font-weight: bold;
    }
    .purple-badge {
        background-color: #c084fc;
        border: 1px solid #c084fc;
        color: #000000;
        font-weight: bold;
    }
    .aqua-badge {
        background-color: #99e6e6;
        border: 1px solid #99e6e6;
        color: #000000;
        font-weight: bold;
    }
    .orange-badge {
        background-color: #FFE5CC; /* Light pastel orange */
        border: 1px solid #FFA500; /* Classic orange border */
        color: #000000;            /* Black text */
        font-weight: bold;
    }
    .ticker-name { font-weight: bold; color: #ffffff; margin-right: 4px; }
    .ticker-rs { color: #4ecdc4; font-weight: normal; }
    table { width:100%; border-collapse: collapse; }
    th { padding: 4px 8px !important; background-color: #1f77b4; color: white; font-size: 12px; }
    td { padding: 2px 8px !important; border-bottom: 1px solid #333; font-size: 12px; }
    </style>
    """, unsafe_allow_html=True)

    # Compute weighted average group rank for all setup tickers
    # Each ticker may appear in multiple groups; use the best (lowest) rank among its groups
    if global_setup_count > 0 and 'df_main' in dir():
        industry_rank_map = dict(zip(df_main['Industry'], df_main['Current Rank']))
        rank_sum = 0
        for sym in global_setup_tickers:
            industries = global_setup_ticker_groups.get(sym, [])
            ranks = [industry_rank_map[ind] for ind in industries if ind in industry_rank_map]
            rank_sum += min(ranks) if ranks else 0
        setup_avg_rank = round(rank_sum / global_setup_count, 1)
        setup_rank_str = f'(avgRank = {setup_avg_rank})'
    else:
        setup_rank_str = ''

    # ── DEBUG: avgRank calculation breakdown ─────────────────────────────
    # if global_setup_count > 0 and 'df_main' in dir():
    #     with st.sidebar.expander("🐛 avgRank Debug", expanded=False):
    #         debug_rows = []
    #         for sym in sorted(global_setup_tickers):
    #             industries = global_setup_ticker_groups.get(sym, [])
    #             ranks = [(ind, industry_rank_map.get(ind)) for ind in industries if ind in industry_rank_map]
    #             ranks_only = [r for _, r in ranks]
    #             best_rank = min(ranks_only) if ranks_only else 0
    #             debug_rows.append({
    #                 "Ticker": sym,
    #                 "Industries (rank)": ", ".join(f"{ind}({r})" for ind, r in ranks),
    #                 "Min Rank Used": best_rank
    #             })

    #         st.dataframe(pd.DataFrame(debug_rows), use_container_width=True, hide_index=True)

    #         st.markdown(
    #             f"**Sum of min ranks** = {rank_sum}  \n"
    #             f"**Setup count** = {global_setup_count}  \n"
    #             f"**avgRank** = {rank_sum} / {global_setup_count} = **{setup_avg_rank}**"
    #         )
    # ─────────────────────────────────────────────────────────────────────

    st.markdown(
        f'<div style="text-align: right; font-size: 20px; color: #888888; margin-bottom: 4px; font-family: monospace;">'
        f'Setup = <span style="color: #4ecdc4; font-weight: bold;">{global_setup_count}</span>'
        f'<span style="color: #888888; font-size: 16px; margin-left: 6px;">{setup_rank_str}</span></div>',
        unsafe_allow_html=True
    )

    table_html = """<table>
    <thead><tr>
    <th style="text-align: center; width: 30px;">#</th>
    <th style="text-align: left;">Industry</th>
    <th style="text-align: center; width: 40px;">RS</th>
    <th style="text-align: center; width: 40px;">1W</th>
    <th style="text-align: center; width: 40px;">1M</th>
    <th style="text-align: left;">Tickers (RS > 80)</th>
    <th style="text-align: left; width: 190px;">21ema_Valid</th>
    <th style="text-align: left; width: 190px;">21ema_Cloud</th>
    <th style="text-align: left; width: 190px;">21ema_Wick</th>
    <th style="text-align: left; width: 190px;">50ma_Bounce</th>
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
            # Check if it's in the top 20 industries and the 1M value is greater than +20
            if shift_1m >= 20 and row_num <= 20:
                rank_str_1m = (
                    f'<span style="color: #00FF00; font-weight: bold; '
                    f'border: 2px solid #00FF00; border-radius: 50%; '
                    f'display: inline-flex; align-items: center; justify-content: center; '
                    f'width: 32px; height: 32px;">+{shift_1m}</span>'
                )
            else:
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
        top_5_cloud = sorted_cloud if show_all_setups else sorted_cloud[:5]
        
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

        # ================================
        # 21 EMA CLOUD COLUMN (new column)
        # ================================
        cloud_21ema_html = ""
        sorted_cloud_21ema = sorted(item["Cloud21EMA"], key=lambda sym: rs_lookup.get(sym, 0), reverse=True)
        top_5_cloud_21ema = sorted_cloud_21ema if show_all_setups else sorted_cloud_21ema[:5]

        for cloud_sym in top_5_cloud_21ema:
            cloud_rs = rs_lookup.get(cloud_sym, 0)

            if cloud_sym in LIME_STOCKS:
                cloud_21ema_html += (
                    f'<div class="ticker-badge lime-badge">'
                    f'<span class="ticker-name" style="color: #000000; font-weight: bold;">{cloud_sym}</span>'
                    f'<span class="ticker-rs" style="color: #000000; font-weight: bold; margin-left: 5px;">{cloud_rs:.0f}</span>'
                    f'</div>'
                )
            elif cloud_sym in KNOWN_STOCKS:
                cloud_21ema_html += (
                    f'<div class="ticker-badge purple-badge">'
                    f'<span class="ticker-name" style="color: #000000; font-weight: bold;">{cloud_sym}</span>'
                    f'<span class="ticker-rs" style="color: #7e22ce; font-weight: bold;">{cloud_rs:.0f}</span>'
                    f'</div>'
                )
            else:
                cloud_21ema_html += (
                    f'<div class="ticker-badge">'
                    f'<span class="ticker-name">{cloud_sym}</span>'
                    f'<span class="ticker-rs">{cloud_rs:.0f}</span>'
                    f'</div>'
                )
        bg_color = "#262730" if row_num % 2 == 0 else "#0e1117"
        
        # ================================
        # 21 EMA WICK COLUMN (new column)
        # ================================
        cloud_wick_html = ""
        sorted_cloud_wick = sorted(item["CloudWick"], key=lambda sym: rs_lookup.get(sym, 0), reverse=True)
        top_5_cloud_wick = sorted_cloud_wick if show_all_setups else sorted_cloud_wick[:5]

        for cloud_sym in top_5_cloud_wick:
            cloud_rs = rs_lookup.get(cloud_sym, 0)

            if cloud_sym in LIME_STOCKS:
                cloud_wick_html += (
                    f'<div class="ticker-badge lime-badge">'
                    f'<span class="ticker-name" style="color: #000000; font-weight: bold;">{cloud_sym}</span>'
                    f'<span class="ticker-rs" style="color: #000000; font-weight: bold; margin-left: 5px;">{cloud_rs:.0f}</span>'
                    f'</div>'
                )
            elif cloud_sym in KNOWN_STOCKS:
                cloud_wick_html += (
                    f'<div class="ticker-badge aqua-badge">'
                    f'<span class="ticker-name" style="color: #000000; font-weight: bold;">{cloud_sym}</span>'
                    f'<span class="ticker-rs" style="color: #0f766e; font-weight: bold;">{cloud_rs:.0f}</span>'
                    f'</div>'
                )
            else:
                cloud_wick_html += (
                    f'<div class="ticker-badge">'
                    f'<span class="ticker-name">{cloud_sym}</span>'
                    f'<span class="ticker-rs">{cloud_rs:.0f}</span>'
                    f'</div>'
                )

        # ================================
        # 50MA BOUNCE COLUMN (new column)
        # ================================
        ma50_bounce_html = ""
        sorted_ma50_bounce = sorted(item["MA50Bounce"], key=lambda sym: rs_lookup.get(sym, 0), reverse=True)
        top_5_ma50_bounce = sorted_ma50_bounce if show_all_setups else sorted_ma50_bounce[:5]

        for cloud_sym in top_5_ma50_bounce:
            cloud_rs = rs_lookup.get(cloud_sym, 0)

            if cloud_sym in LIME_STOCKS:
                ma50_bounce_html += (
                    f'<div class="ticker-badge lime-badge">'
                    f'<span class="ticker-name" style="color: #000000; font-weight: bold;">{cloud_sym}</span>'
                    f'<span class="ticker-rs" style="color: #000000; font-weight: bold; margin-left: 5px;">{cloud_rs:.0f}</span>'
                    f'</div>'
                )
            elif cloud_sym in KNOWN_STOCKS:
                ma50_bounce_html += (
                    f'<div class="ticker-badge orange-badge">'
                    f'<span class="ticker-name" style="color: #111111; font-weight: bold;">{cloud_sym}</span>'
                    f'<span class="ticker-rs" style="color: #004d26; font-weight: bold;">{cloud_rs:.0f}</span>'
                    f'</div>'
                )
            else:
                ma50_bounce_html += (
                    f'<div class="ticker-badge">'
                    f'<span class="ticker-name">{cloud_sym}</span>'
                    f'<span class="ticker-rs">{cloud_rs:.0f}</span>'
                    f'</div>'
                )

        table_html += f"""<tr style="background-color: {bg_color};">
        <td style="text-align: center; color: #888; font-weight: bold;">{row_num}</td>
        <td style="font-weight: bold; color: #ffffff;">{row['Industry']}</td>
        <td style="text-align: center; color: #4ecdc4; font-weight: bold;">{row['Group RS']:.1f}</td>
        <td style="text-align: center; vertical-align: middle;">{rank_str}</td>
        <td style="text-align: center; vertical-align: middle;">{rank_str_1m}</td>
        <td>{ticker_html}</td>
        <td>{cloud_html}</td>
        <td>{cloud_21ema_html}</td>
        <td>{cloud_wick_html}</td>
        <td>{ma50_bounce_html}</td></tr>"""

    table_html += "</tbody></table>"
    st.markdown(table_html, unsafe_allow_html=True)

# 7. EXTRA SEPARATE PATTERNS SCANNING BLOCK
#st.markdown("---")
#st.markdown("### 🔍 Technical Pattern Screener (KNOWN_STOCKS Database)")

# ================================
# PPP MINI CHART: OHLCV DATA FETCH
# ================================
@st.cache_data(ttl=3600)
def get_ppp_ohlcv_json(ticker):
    try:
        df = yf.download(ticker, period="3mo", interval="1d", progress=False)
        if df.empty:
            return "[]"
        df = df.tail(42)  # ~2 months of trading days
        records = []
        for ts, row in df.iterrows():
            records.append({
                "time":  ts.strftime("%Y-%m-%d"),
                "open":  round(float(row["Open"].iloc[0])  if hasattr(row["Open"],  "iloc") else float(row["Open"]),  2),
                "high":  round(float(row["High"].iloc[0])  if hasattr(row["High"],  "iloc") else float(row["High"]),  2),
                "low":   round(float(row["Low"].iloc[0])   if hasattr(row["Low"],   "iloc") else float(row["Low"]),   2),
                "close": round(float(row["Close"].iloc[0]) if hasattr(row["Close"], "iloc") else float(row["Close"]), 2),
            })
        import json
        return json.dumps(records)
    except Exception:
        return "[]"

@st.cache_data(ttl=3600)
def get_gapper_ohlcv_json(ticker):
    try:
        df = yf.download(ticker, period="3mo", interval="1d", progress=False)
        if df.empty:
            return "[]"
        df = df.tail(42)
        records = []
        for ts, row in df.iterrows():
            records.append({
                "time":  ts.strftime("%Y-%m-%d"),
                "open":  round(float(row["Open"].iloc[0])  if hasattr(row["Open"],  "iloc") else float(row["Open"]),  2),
                "high":  round(float(row["High"].iloc[0])  if hasattr(row["High"],  "iloc") else float(row["High"]),  2),
                "low":   round(float(row["Low"].iloc[0])   if hasattr(row["Low"],   "iloc") else float(row["Low"]),   2),
                "close": round(float(row["Close"].iloc[0]) if hasattr(row["Close"], "iloc") else float(row["Close"]), 2),
            })
        import json
        return json.dumps(records)
    except Exception:
        return "[]"
    
@st.cache_data(ttl=3600)
def compute_two_botak_history(stocks_list, _ticker_dfs):
    try:
        if not _ticker_dfs:
            return pd.DataFrame()

        all_series = []
        errors = []  # ADD THIS
        for ticker, df in _ticker_dfs.items():
            if not all(col in df.columns for col in ['Open', 'High', 'Low', 'Close']):
                continue
            if len(df) < 2:
                continue

            try:  # ADD INNER TRY to catch per-ticker errors
                botak = (
                    (abs(df['Close'] - df['High']) < 0.05) &
                    (df['Close'] > df['Open'])
                )
                percentile = (
                    (df['Close'] > df['Open']) &
                    (((df['Close'] - df['Open']) /
                      ((df['High'] - df['Open']).replace(0, 0.001))) > 0.9)
                )
                two_botak_series = (
                    ((botak & botak.shift(1)) |
                     (botak & percentile.shift(1)) |
                     (percentile & botak.shift(1)) |
                     (percentile & percentile.shift(1))) &
                    (df['Close'] > 20)
                ).astype(int)

                all_series.append(two_botak_series)
            except Exception as e:
                errors.append(f"{ticker}: {e}")  # ADD THIS
                continue

        #st.write(f"all_series count: {len(all_series)}, errors sample: {errors[:3]}")  # ADD THIS

        if not all_series:
            return pd.DataFrame()

        combined = pd.concat(all_series, axis=1).fillna(0)
        daily_counts = combined.sum(axis=1)

        result = daily_counts.tail(60).reset_index()
        result.columns = ["Date", "Two Botak Count"]
        result["Date"] = result["Date"].dt.strftime("%Y-%m-%d")
        return result
    except Exception as e:
        st.write(f"OUTER ERROR: {e}")  # ADD THIS
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def compute_engulfing_history(stocks_list, _ticker_dfs):
    try:
        if not _ticker_dfs:
            return pd.DataFrame()

        all_2x = []
        all_3x = []

        for ticker, df in _ticker_dfs.items():
            if not all(col in df.columns for col in ['Open', 'High', 'Low', 'Close']):
                continue
            if len(df) < 30:
                continue

            bullish_engulfing = (
                (df['Open'] < df['Low'].shift(1)) &
                (df['Close'] > df['High'].shift(1))
            )

            # Rolling count of engulfing candles in last 30 days
            engulf_count = bullish_engulfing.rolling(30).sum()

            # For the "close above prior engulf closes" condition:
            # Get the last engulfing close via a forward-filled masked series
            eng_close = df['Close'].where(bullish_engulfing, other=pd.NA).ffill()
            eng_close_2 = df['Close'].where(bullish_engulfing, other=pd.NA).shift(1).ffill()
            eng_close_3 = df['Close'].where(bullish_engulfing, other=pd.NA).shift(2).ffill()

            two_engulf = (
                (engulf_count >= 2) &
                (df['Close'] > 20) &
                (df['Close'] > eng_close.shift(1)) &   # above most recent prior
                (df['Close'] > eng_close_2.shift(1))
            ).astype(int)

            three_engulf = (
                (engulf_count >= 3) &
                (df['Close'] > 20) &
                (df['Close'] > eng_close.shift(1)) &
                (df['Close'] > eng_close_2.shift(1)) &
                (df['Close'] > eng_close_3.shift(1))
            ).astype(int)

            all_2x.append(two_engulf)
            all_3x.append(three_engulf)

        if not all_2x:
            return pd.DataFrame()

        count_2x = pd.concat(all_2x, axis=1).fillna(0).sum(axis=1)
        count_3x = pd.concat(all_3x, axis=1).fillna(0).sum(axis=1)

        # Align on common index, take last 60 rows
        result = pd.DataFrame({
            "Date": count_2x.index,
            "2x Engulfing Count": count_2x.values,
            "3x Engulfing Count": count_3x.values
        }).tail(60)
        result["Date"] = pd.to_datetime(result["Date"]).dt.strftime("%Y-%m-%d")
        return result.reset_index(drop=True)

    except Exception as e:
        print(e)
        return pd.DataFrame()
    
@st.cache_data(ttl=3600)
def compute_powertrend_history(stocks_list, _ticker_dfs):
    try:
        if not _ticker_dfs:
            return pd.DataFrame()

        # Compute full powertrend boolean series per ticker ONCE
        all_series = []
        for ticker, df in _ticker_dfs.items():
            if len(df) < 52:
                continue
            powerma = df['Close'].ewm(span=50, adjust=False).mean()
            gradientPct = ((powerma - powerma.shift(1)) / powerma.shift(1)) * 100
            pt_series = (
                (powerma > powerma.shift(1)) &
                (abs(gradientPct) >= 1.0) &
                (df['Close'] >= 20)
            ).astype(int)
            all_series.append(pt_series)

        if not all_series:
            return pd.DataFrame()

        # Sum across all tickers for each date — one operation
        combined = pd.concat(all_series, axis=1).fillna(0)
        daily_counts = combined.sum(axis=1)

        result = daily_counts.tail(60).reset_index()
        result.columns = ["Date", "PowerTrend Count"]
        result["Date"] = result["Date"].dt.strftime("%Y-%m-%d")
        return result.iloc[::-1].reset_index(drop=True).iloc[::-1]  # keep chronological
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def compute_leader_history(stocks_list, _ticker_dfs, benchmark_df_leader):
    try:
        if not _ticker_dfs:
            return pd.DataFrame()

        all_series = []

        for ticker, df in _ticker_dfs.items():
            if len(df) < 250:
                continue
            try:
                rs = df['Close'] / benchmark_df_leader['Close']
                rsMA = rs.ewm(span=21, adjust=False).mean()
                histNH = rs.rolling(250).max()
                sma50 = df['Close'].rolling(50).mean()
                sma200 = df['Close'].rolling(200).mean()

                circleCond = (rs == histNH)
                circleCount30 = circleCond.rolling(30).sum()
                twoCircles30 = circleCount30 >= 2

                leader_series = (
                    (twoCircles30 | circleCond) &
                    (rs > rsMA) &
                    (df['Close'] > sma50) &
                    (df['Close'] > sma200) &
                    (df['Close'] >= 20)
                ).astype(int)

                all_series.append(leader_series)
            except Exception:
                continue

        if not all_series:
            return pd.DataFrame()

        combined = pd.concat(all_series, axis=1).fillna(0)
        daily_counts = combined.sum(axis=1)

        result = daily_counts.tail(60).reset_index()
        result.columns = ["Date", "Leader Count"]
        result["Date"] = result["Date"].dt.strftime("%Y-%m-%d")
        return result
    except Exception:
        return pd.DataFrame()
    
# ==============================================================================
# 8. HISTORICAL KNOW_TOTAL_COUNT 30-DAY CHART (Completely New Logic at Bottom)
# ==============================================================================
@st.cache_data(ttl=3600)
def compute_historical_know_counts(stocks_list, _ticker_dfs):
    try:
        # Attach SMA columns needed by this function only (non-destructive copy)
        enriched_dfs = {}
        for ticker, df in _ticker_dfs.items():
            if ticker.startswith('^'):   # skip benchmark indices
                continue
            if len(df) >= 261:
                df2 = df.copy()
                df2["SMA_50"]  = round(df2['Close'].rolling(window=50).mean(), 2)
                df2["SMA_200"] = round(df2['Close'].rolling(window=200).mean(), 2)
                enriched_dfs[ticker] = df2
        ticker_dfs = enriched_dfs  # shadow with enriched version for rest of function

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
                "Minervini Count": day_total_count,
                "Positive Pct": round(day_pos_pct, 1)
            })

        return pd.DataFrame(historical_records)
    except Exception as e:
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def compute_setup_avgrank_history(all_data_snapshot, ticker_dfs_all, benchmark_df_all, rs_length, setup_tickers, ticker_industry_groups):
    try:
        if not ticker_dfs_all or not all_data_snapshot or not setup_tickers:
            return pd.DataFrame()

        bench_close = benchmark_df_all['Close']

        # industry -> list of tickers (from INDUSTRIES, via all_data_snapshot's Industry names)
        industry_tickers_map = {
            item["Industry"]: list(INDUSTRIES.get(item["Industry"], []))
            for item in all_data_snapshot
        }
        all_industries = list(industry_tickers_map.keys())

        top_n = 5  # mirror sidebar default

        # For each industry, compute the FULL daily Group RS series
        # using the SAME normalization formula as get_rs_and_cloud_data_cached:
        #   total_score = int(((99-1)*(rs-ll)/(hh-ll)) + 1)
        industry_daily_grouprs = {}

        for industry in all_industries:
            tickers_in_group = industry_tickers_map.get(industry, [])
            ticker_scores_list = []

            for sym in tickers_in_group:
                df = ticker_dfs_all.get(sym)
                if df is None or len(df) < rs_length + 5:
                    continue

                aligned, bench_aligned = df['Close'].align(bench_close, join='inner')
                if len(aligned) < rs_length:
                    continue

                rs_ratio = aligned / bench_aligned
                hh = rs_ratio.rolling(window=rs_length).max()
                ll = rs_ratio.rolling(window=rs_length).min()
                denom = hh - ll

                # Match live formula exactly: int(((99-1)*(rs-ll)/(hh-ll)) + 1)
                raw = ((99 - 1) * (rs_ratio - ll) / denom.replace(0, np.nan)) + 1
                score = raw.apply(lambda x: int(x) if pd.notna(x) else 0)
                ticker_scores_list.append(score)

            if not ticker_scores_list:
                continue

            scores_df = pd.concat(ticker_scores_list, axis=1).fillna(0)

            def top_n_mean(row):
                vals = sorted(row.dropna().values, reverse=True)
                top = vals[:top_n]
                return sum(top) / len(top) if top else 0

            group_rs_series = scores_df.apply(top_n_mean, axis=1)
            industry_daily_grouprs[industry] = group_rs_series

        if not industry_daily_grouprs:
            return pd.DataFrame()

        # Wide DataFrame: columns = industries, rows = dates
        wide_df = pd.DataFrame(industry_daily_grouprs).dropna(how='all')

        full_timeline = bench_close.index
        days_to_compute = min(60, len(wide_df))

        records = []
        for i in range(days_to_compute - 1, -1, -1):
            target_date = full_timeline[-1 - i]

            try:
                loc = wide_df.index.get_loc(target_date)
                if isinstance(loc, slice):
                    loc = loc.stop - 1
                day_scores = wide_df.iloc[loc]
            except Exception:
                continue

            day_scores = day_scores.dropna()
            if day_scores.empty:
                continue

            # Rank: highest Group RS = rank 1 (matches df_main['Current Rank'] logic)
            day_ranks = day_scores.rank(ascending=False, method='min').astype(int)

            # Fixed set of setup tickers (same as global_setup_tickers, frozen to "today")
            rank_sum = 0
            setup_count = 0
            for sym in setup_tickers:
                industries = ticker_industry_groups.get(sym, [])
                ranks = [int(day_ranks[ind]) for ind in industries if ind in day_ranks.index]
                if not ranks:
                    continue
                rank_sum += min(ranks)
                setup_count += 1

            avg_rank = round(rank_sum / setup_count, 1) if setup_count > 0 else 0
            records.append({
                "Date": target_date.strftime("%Y-%m-%d"),
                "Avg Rank": avg_rank,
            })

        return pd.DataFrame(records)
    except Exception:
        return pd.DataFrame()

st.markdown("---")

#st.markdown("#### 📊 Industry RS Quadrant Map (Weekly vs Monthly)")

# ── Build per-industry (weekly_rs, monthly_rs) from all_data ─────────────────
# weekly_rs  = current Group RS (top-N average of today's normalised RS scores)
# monthly_rs = 1-month-ago Group RS (top-N average of 1-month-ago normalised RS scores)
quad_points = []
for item in all_data:
    industry   = item["Industry"]
    weekly_rs  = float(item["Group RS"])      # current  (≈ weekly proxy)
    monthly_rs = float(item["Group RS 1M"])   # 1-month ago (≈ monthly proxy)
    quad_points.append({
        "industry"  : industry,
        "weekly_rs" : round(weekly_rs,  1),
        "monthly_rs": round(monthly_rs, 1),
    })
 
if quad_points:
    xs     = [p["weekly_rs"]  for p in quad_points]
    ys     = [p["monthly_rs"] for p in quad_points]
    labels = [p["industry"]   for p in quad_points]
 
    # Colour each dot by quadrant (matching photo tones)
    dot_colors = []
    for p in quad_points:
        w, m = p["weekly_rs"], p["monthly_rs"]
        if   w >= 50 and m >= 50: dot_colors.append("#1a5c35")   # Strong       — dark green
        elif w >= 50 and m <  50: dot_colors.append("#1a5c35")   # Improving    — dark green
        elif w <  50 and m >= 50: dot_colors.append("#8b1a1a")   # Weakening    — dark rose
        else:                     dot_colors.append("#8b1a1a")   # Weak         — dark salmon
 
    fig = go.Figure()
 
    # ── Quadrant background rectangles ───────────────────────────────────────
    # Bottom-left  = Weak       — salmon / coral pink (matching photo)
    fig.add_shape(type="rect", x0=0,  y0=0,   x1=50,  y1=50,
                  fillcolor="rgba(255,160,160,0.55)", line_width=0, layer="below")
    # Top-left     = Weakening  — lighter rose (matching photo)
    fig.add_shape(type="rect", x0=0,  y0=50,  x1=50,  y1=100,
                  fillcolor="rgba(255,182,193,0.35)", line_width=0, layer="below")
    # Bottom-right = Improving  — light mint green (matching photo)
    fig.add_shape(type="rect", x0=50, y0=0,   x1=100, y1=50,
                  fillcolor="rgba(144,238,144,0.35)", line_width=0, layer="below")
    # Top-right    = Strong     — deeper green (matching photo)
    fig.add_shape(type="rect", x0=50, y0=50,  x1=100, y1=100,
                  fillcolor="rgba(144,238,144,0.60)", line_width=0, layer="below")
 
    # ── Divider lines ─────────────────────────────────────────────────────────
    fig.add_shape(type="line", x0=50, y0=0,  x1=50,  y1=100,
                  line=dict(color="rgba(200,200,200,0.55)", width=1.2, dash="dot"))
    fig.add_shape(type="line", x0=0,  y0=50, x1=100, y1=50,
                  line=dict(color="rgba(200,200,200,0.55)", width=1.2, dash="dot"))
 
    # ── Quadrant corner labels ────────────────────────────────────────────────
    quad_label_cfg = dict(
        xref="x", yref="y", showarrow=False,
        font=dict(size=15, color="rgba(60,60,60,0.65)"),
        xanchor="center",
    )
    q_strong    = sum(1 for p in quad_points if p["weekly_rs"] >= 50 and p["monthly_rs"] >= 50)
    q_improving = sum(1 for p in quad_points if p["weekly_rs"] >= 50 and p["monthly_rs"] <  50)
    q_weakening = sum(1 for p in quad_points if p["weekly_rs"] <  50 and p["monthly_rs"] >= 50)
    q_weak      = sum(1 for p in quad_points if p["weekly_rs"] <  50 and p["monthly_rs"] <  50)

    fig.add_annotation(x=25,  y=96, text=f"<b>Weakening ({q_weakening})</b>",  **quad_label_cfg)
    fig.add_annotation(x=75,  y=96, text=f"<b>Strong ({q_strong})</b>",        **quad_label_cfg)
    fig.add_annotation(x=25,  y=4,  text=f"<b>Weak ({q_weak})</b>",            **quad_label_cfg)
    fig.add_annotation(x=75,  y=4,  text=f"<b>Improving ({q_improving})</b>",  **quad_label_cfg)
 
    # ── Scatter dots with industry name labels ────────────────────────────────
    fig.add_trace(go.Scatter(
        x=xs,
        y=ys,
        mode="markers+text",
        text=labels,
        textposition="top center",
        textfont=dict(size=10, color="#111111"),
        marker=dict(
            color=dot_colors,
            size=7,
            line=dict(width=0.8, color="rgba(255,255,255,0.6)"),
            opacity=0.90,
        ),
        hovertemplate=(
            "<b>%{text}</b><br>"
            "Weekly RS : %{x:.1f}<br>"
            "Monthly RS: %{y:.1f}"
            "<extra></extra>"
        ),
        showlegend=False,
    ))
 
    # ── Chart layout ──────────────────────────────────────────────────────────
    fig.update_layout(
        title=dict(
            text="Industry RS — Weekly vs Monthly",
            x=0.5,
            xanchor="center",
            font=dict(size=16, color="#ffffff"),
        ),
        xaxis=dict(
            title="Weekly RS",
            range=[0, 100],
            dtick=10,
            showgrid=True,
            gridcolor="rgba(120,120,120,0.18)",
            zeroline=False,
            tickfont=dict(color="#aaaaaa", size=11),
            title_font=dict(color="#aaaaaa", size=12),
        ),
        yaxis=dict(
            title="Monthly RS",
            range=[0, 100],
            dtick=10,
            showgrid=True,
            gridcolor="rgba(120,120,120,0.18)",
            zeroline=False,
            tickfont=dict(color="#aaaaaa", size=11),
            title_font=dict(color="#aaaaaa", size=12),
        ),
        plot_bgcolor ="rgba(20,22,30,1)",
        paper_bgcolor="rgba(13,17,23,0)",
        height=900,
        margin=dict(l=55, r=25, t=65, b=55),
        font=dict(color="#cccccc"),
        hoverlabel=dict(
            bgcolor="#1e2030",
            bordercolor="#555555",
            font_size=12,
            font_color="#ffffff",
        ),
    )
 
    st.plotly_chart(fig, use_container_width=True)
 
else:
    st.info("No industry RS data available to render the quadrant map.")

st.markdown("---")
#st.markdown(f"#### 🎯 Stage Analysis")

if breadth_total > 0:
    # ── Stage: single stacked bar ─────────────────────────────────────────
    stage_order  = [1, 2, 3, 4]
    stage_colors = {1: "#a9a9a9", 2: "#378ADD", 3: "#EF9F27", 4: "#FF69B4"}
    stage_labels = {1: "S1", 2: "S2", 3: "S3", 4: "S4"}

    bar_total = sum(stage_counts.get(s, 0) for s in stage_order)

    if bar_total > 0:
        segs = [
            {"s": s, "cnt": stage_counts.get(s, 0),
             "pct": stage_counts.get(s, 0) / bar_total * 100,
             "color": stage_colors[s]}
            for s in stage_order
        ]

        bar_segs = ""
        legend = ""
        
        for i, seg in enumerate(segs):
            # 1. Build the bar segment
            r = ("border-radius:999px 0 0 999px;" if i == 0
                 else "border-radius:0 999px 999px 0;" if i == len(segs) - 1
                 else "")
            bar_segs += (
                f"<div style='width:{seg['pct']:.2f}%; background:{seg['color']};"
                f"height:100%; {r}'></div>"
            )

            # 2. Build the perfectly aligned label area below it
            # Hide text details entirely if the percentage is 0 to avoid overlapping strings
            display_style = "display:flex;" if seg['pct'] > 0 else "display:none;"
            
            legend += (
                f"<div style='width:{seg['pct']:.2f}%; {display_style} flex-direction:column;"
                f"align-items:center; text-align:center; box-sizing:border-box; padding:0 2px; overflow:hidden;'>"
                f"<div style='display:flex;align-items:center;gap:5px;justify-content:center; white-space:nowrap;'>"
                f"<span style='width:8px;height:8px;border-radius:50%;"
                f"background:{seg['color']};display:inline-block;flex-shrink:0;'></span>"
                f"<span style='font-size:13px;font-weight:500;color:#ffffff;'>"
                f"{stage_labels[seg['s']]}</span></div>"
                f"<span style='font-size:11px;color:#888888;white-space:nowrap;'>"
                f"{seg['cnt']} · {seg['pct']:.0f}%</span>"
                f"</div>"
            )

        st.markdown(
            f"<div style='padding:8px 0 4px; width:100%;'>"
            f"<div style='text-align: center; font-size: 30px; font-weight: bold; color: #ffffff; margin-bottom: 18px;'>Stage</div>"
            f"<div style='width:100%;height:12px;display:flex;"
            f"overflow:hidden;border-radius:999px;'>{bar_segs}</div>"
            f"<div style='display:flex; width:100%; margin-top:10px;'>"
            f"{legend}</div></div>",
            unsafe_allow_html=True
        )

else:
    st.info("Insufficient data to compute breadth & stage analysis.")

with st.spinner("Scanning pattern anomalies across known instruments..."):
    results       = timed("process_pattern_scanners",      process_pattern_scanners,      stocks_tuple, ticker_dfs_shared, benchmark_df_shared)
    # historical_df   = compute_historical_know_counts(stocks_tuple, ticker_dfs_shared)   # moved here: renders first
    # two_botak_hist  = compute_two_botak_history(stocks_tuple, ticker_dfs_shared)
    # engulf_hist     = compute_engulfing_history(stocks_tuple, ticker_dfs_shared)
    # powertrend_hist = compute_powertrend_history(stocks_tuple, ticker_dfs_shared)
    # leader_hist     = compute_leader_history(stocks_tuple, ticker_dfs_shared, benchmark_df_shared)
    b_list, e2_list, e3_list, pt_list, ptne_list, vt_list, ppp_list, leader_list, gapper_list = results[:9]
    b_yest, e2_yest, e3_yest, pt_yest, ptne_yest, vt_yest, ppp_yest, leader_yest, gapper_yest = results[9:18]
    know_pos_pct, know_positive_count, know_total_count, email_content_stocks, email_content_removed, extra_52wk_high_symbols, extra_52wk_high_removed, pct_above_ema200, leader_rs_nh_matches, gapper_gap_levels, ath_list, ath_yest = results[18:]

st.markdown("---")

# ==============================================================================
# 11. MARKET REGIME REFERENCE TABLE (Dynamic Highlight)
# ==============================================================================
#st.markdown("---")

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

#st.markdown(f"#### 🧭 Market Regime ({pct_above_ema200:.2f}%)")
if highlight_idx in [4, 3]:
    pct_color = "#90EE90"
elif highlight_idx in [2, 1]:
    pct_color = "#EF9F27"
else:
    pct_color = "#FF6B6B"

st.markdown(
    f"""
    <h4>
        🧭 Market Regime
        <span style="color:{pct_color}; font-weight:bold;">
            ({pct_above_ema200:.2f}%)
        </span>
    </h4>
    """,
    unsafe_allow_html=True
)

# 1. Define raw data exactly from your reference image
regime_data = {
    "Market Condition": [
        "Above 200 EMA > 70%",
        "Above 200 EMA > 60%",
        "Above 200 EMA 50–60%",
        "Above 200 EMA 40–50%",
        "Above 200 EMA < 40%"
    ],
    "What to do": [
        "Strong bull participation",
        "Good swing trading environment",
        "Market improving",
        "Recovery attempt",
        "Be cautious, focus only on best setups"
    ]
}

# 2. Convert to DataFrame
df_regime = pd.DataFrame(regime_data)

# 4. Create a styling function to apply the lime background
def highlight_current_regime(row):
    pct = pct_above_ema200

    is_highlight = False
    bg = ""

    if pct > 70 and row["Market Condition"] == "Above 200 EMA > 70%":
        bg = "#90EE90"
        is_highlight = True
    elif pct > 60 and row["Market Condition"] == "Above 200 EMA > 60%":
        bg = "#90EE90"
        is_highlight = True
    elif 50 <= pct <= 60 and row["Market Condition"] == "Above 200 EMA 50–60%":
        bg = "#FFD8A8"
        is_highlight = True
    elif 40 <= pct < 50 and row["Market Condition"] == "Above 200 EMA 40–50%":
        bg = "#FFD8A8"
        is_highlight = True
    elif pct < 40 and row["Market Condition"] == "Above 200 EMA < 40%":
        bg = "#FFCCCC"
        is_highlight = True

    if is_highlight:
        return [f"background-color: {bg}; color: #000000; font-weight: bold;"] * len(row)
    else:
        return [""] * len(row)

# 5. Apply the style and render via Streamlit dataframe (handles styling better than st.table)
styled_df = df_regime.style.apply(highlight_current_regime, axis=1)

st.dataframe(
    styled_df,
    use_container_width=False,
    width=520,
    hide_index=True,
    column_config={
        "Market Condition": st.column_config.Column(width=200),
        "What to do": st.column_config.Column(width=300),
    }
)

st.markdown("---")

st.markdown(
    f"#### ⭐ Minervini ("
    f"Positive Pct = {know_pos_pct:.1f}% ... "
    #f"+ve Count: {know_positive_count} ... "
    f"Total = {know_total_count} ... "
    f"ATH = {len(ath_list)})"
)

if email_content_stocks or email_content_removed:
    minervini_html = ""
    
    # 1. Active Symbols Layout (Sorted Alphabetically by the ticker name)
    for sym, is_new_addition, is_positive_today in sorted(email_content_stocks, key=lambda x: x[0]):
        
        # Determine up logo priority: Red if in ath_list, Green if positive today, otherwise empty
        if sym in ath_list:
            up_logo = "<span style='color:#FF4B4B; margin-right:4px; font-weight:bold;'>▲</span>"
        elif is_positive_today:
            up_logo = "<span style='color:#00FF00; margin-right:4px; font-weight:bold;'>▲</span>"
        else:
            up_logo = ""
        
        if is_new_addition:
            minervini_html += f'<div class="ticker-badge new-pattern-badge">{up_logo}{sym}</div>'
        else:
            minervini_html += f'<div class="ticker-badge">{up_logo}{sym}</div>'
            
    # 2. Dropped/Removed Symbols Layout (Sorted Alphabetically with line-through)
    for sym in sorted(email_content_removed):
        minervini_html += f'<div class="ticker-badge removed-badge">{sym}</div>'
        
    st.markdown(minervini_html, unsafe_allow_html=True)
else:
    st.info("No active setups discovered.")

#st.markdown("---")
st.write("")

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

# st.markdown(f"#### 🌟 ATH , but fail Minervini criteria ({len(extra_52wk_high_symbols)})")
# # Render if there are either active items OR removed items to show
# if extra_52wk_high_symbols or extra_52wk_high_removed:
#     extra_html = ""
    
#     # 1. Render Active Symbols (Sorted alphabetically)
#     for sym, is_new_addition_52w in sorted(extra_52wk_high_symbols, key=lambda x: x[0]):
#         if is_new_addition_52w:
#             # Uses your exact native gold badge class for brand new additions today
#             extra_html += f'<div class="ticker-badge new-pattern-badge">{sym}</div>'
#         else:
#             # Standard dark badge layout for stocks that were already on this list yesterday
#             extra_html += f'<div class="ticker-badge">{sym}</div>'
            
#     # 2. Append Removed Symbols (Sorted alphabetically with the removed badge style)
#     for sym in sorted(extra_52wk_high_removed):
#         extra_html += f'<div class="ticker-badge removed-badge">{sym}</div>'
        
#     st.markdown(extra_html, unsafe_allow_html=True)
# else:
#     st.info("No active setups discovered.")

#st.markdown("---")
st.write("")

# # --- ALL TIME HIGH ---
# st.markdown(f"#### ✨ All Time High Close ({len(ath_list)})")

# if ath_list or ath_yest:
#     html_ath = ""
#     for sym in ath_list:
#         cls = "new-pattern-badge" if sym not in ath_yest else ""
#         html_ath += f'<div class="ticker-badge {cls}">{sym}</div>'

#     removed_ath = [sym for sym in ath_yest if sym not in ath_list]
#     for sym in sorted(removed_ath):
#         html_ath += f'<div class="ticker-badge removed-badge">{sym}</div>'

#     st.markdown(html_ath, unsafe_allow_html=True)
# else:
#     st.info("No active setups discovered.")

# st.write("")

with st.spinner("Computing Historical Known Counts..."):
    historical_df = timed("compute_historical_know_counts", compute_historical_know_counts, stocks_tuple, ticker_dfs_shared)

# ==============================================================================
# 9. AUTOMATED BREADTH MARKET REGIME INTERPRETATION
# ==============================================================================
if not historical_df.empty and len(historical_df) >= 10:
    #st.markdown("#### 🧠 Market Breadth Regime Analysis")
    
    # Isolate trailing 30 days data (or max available) for trend analysis
    sample_df = historical_df.tail(30).copy()
    counts = sample_df["Minervini Count"].tolist()
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
    if ma_short > ma_long and current_count >= ma_long:
        status_color = "#00FF00" # Emerald Green
        status_title = "EXPANDING MOMENTUM"
        action_note = "Market participation is expanding actively. Growth setups have a high probability of immediate follow-through. Lean long."
    elif ma_short < ma_long and current_count <= ma_long:
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
                <span style="color: {status_color}; font-weight: bold; font-size: 1.4em;">{current_count}</span>
                (5-Day Trend Avg: 
                <span style="color: {status_color}; font-weight: bold;">{ma_short:.1f}</span> 
                vs 20-Day Trend Avg: 
                <span style="color: {status_color}; font-weight: bold;">{ma_long:.1f}</span>). <br>
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )
#                <b>Tactical Playbook:</b> {action_note}
#st.markdown("---")
st.write("")

#st.markdown(f"### Minervini Count ({know_total_count})")
if not historical_df.empty:
    chart_df_minervini = historical_df.copy()
    chart_df_minervini["20D MA"] = (
        chart_df_minervini["Minervini Count"]
        .rolling(window=20, min_periods=1)
        .mean()
        .round(1)
    )
    st.line_chart(
        data=chart_df_minervini,
        x="Date",
        y=["Minervini Count", "20D MA"],
        color=["#1f77b4", "#FF4B4B"],
        use_container_width=True
    )
    
    #st.markdown("---")
    
    # 2. THE NEW STANDALONE CHART: Displays the Positive Percentage metric over 90 days
    #st.markdown(f"### Positive Percentage ({know_pos_pct:.1f}%)")
    #st.line_chart(data=historical_df, x="Date", y="Positive Pct", use_container_width=True)
else:
    st.info("Insufficient historical trading records available to draw historical metrics.")

st.markdown("---")



# --- Render Header with Inline Summary Metrics inside Parentheses ---
# header_html = (
#     f"<div style='margin-top:20px; font-size:1.15em; font-weight:bold; display:flex; align-items:center; gap:10px;'>"
#     f"<span>⭐ Minervini Qualified Stocks</span>"
#     f"<span style='font-weight:normal; color:#888;'> "
#     f"(<b style='color:#eee;'>Positive Pct:</b> {know_pos_pct:.1f}% |"
#     f" <b style='color:#eee;'>Positive Count:</b> {know_positive_count} |"
#     f" <b style='color:#eee;'>Minervini Count:</b> {know_total_count})"
#     f"</div>"
# )
# st.markdown(header_html, unsafe_allow_html=True)

@st.cache_data(ttl=3600)
def compute_leader_streaks(leader_list_tuple, ticker_dfs, benchmark_df_input):
    """Return dict of ticker -> consecutive days in leader condition."""
    streaks = {}
    for ticker in leader_list_tuple:
        try:
            df = ticker_dfs.get(ticker)
            if df is None or len(df) < 250:
                streaks[ticker] = 0
                continue

            rs = df['Close'] / benchmark_df_input['Close']
            rsMA = rs.ewm(span=21, adjust=False).mean()
            histNH = rs.rolling(250).max()
            sma50 = df['Close'].rolling(50).mean()
            sma200 = df['Close'].rolling(200).mean()
            circleCond = (rs == histNH)
            cc30 = circleCond.rolling(30).sum() >= 2

            leader_s = (
                (cc30 | circleCond) &
                (rs > rsMA) &
                (df['Close'] > sma50) &
                (df['Close'] > sma200) &
                (df['Close'] >= 20)
            )

            # Count consecutive True from the end
            vals = leader_s.dropna().values
            count = 0
            for v in reversed(vals):
                if v:
                    count += 1
                else:
                    break
            streaks[ticker] = count
        except Exception:
            streaks[ticker] = 0
    return streaks

leader_streaks = timed(
    "compute_leader_streaks",
    compute_leader_streaks,
    tuple(leader_list), ticker_dfs_shared, benchmark_df_shared
)

with st.spinner("Scanning for Leader History..."):
    leader_hist   = timed("compute_leader_history",        compute_leader_history,        stocks_tuple, ticker_dfs_shared, benchmark_df_shared)

#st.write(f"Percentage of stock above EMA200: {pct_above_ema200:.2f}%")

# --- LEADERS SECTION ---
st.markdown(f"#### 🏆 RS Leader = Long term ({len(leader_list)}) ")
st.markdown(f"#### 🔺 Blue Dot = Short term ({len([s for s in leader_rs_nh_matches if s != 'SPY'])})")

if leader_list or leader_yest:

    html_leader = ""

    for sym in leader_list:
        dot = (
            '<span style="'
            'display:inline-block;width:7px;height:7px;'
            'border-radius:50%;background:#FF4B4B;'
            'box-shadow:0 0 5px 2px #FF4B4B;'
            'margin-right:4px;vertical-align:middle;'
            '"></span>'
            if sym in leader_rs_nh_matches and sym != "SPY" else ""
        )

        streak = leader_streaks.get(sym, 0)
        streak_color = "#333333" if sym in (ma50bounce_all | cloudwick_all | cloud21ema_all) else "#888888"
        streak_html = (
            f'<span style="color:{streak_color}; font-size:10px; margin-left:5px;">· {streak}</span>'
            if streak > 0 else ""
        )

        # Priority: orange (50ma_bounce) > aqua (21ema_wick) > purple (21ema_cloud) > default
        if sym in ma50bounce_all:
            html_leader += (
                f'<div class="ticker-badge orange-badge">'
                f'{dot}'
                f'<span style="color:#111111;font-weight:bold;">{sym}</span>'
                f'<span style="color:#004d26;font-weight:bold;">{streak_html}</span>'
                f'</div>'
            )
        elif sym in cloudwick_all:
            html_leader += (
                f'<div class="ticker-badge aqua-badge">'
                f'{dot}'
                f'<span style="color:#000000;font-weight:bold;">{sym}</span>'
                f'<span style="color:#0f766e;font-weight:bold;">{streak_html}</span>'
                f'</div>'
            )
        elif sym in cloud21ema_all:
            html_leader += (
                f'<div class="ticker-badge purple-badge">'
                f'{dot}'
                f'<span style="color:#000000;font-weight:bold;">{sym}</span>'
                f'<span style="color:#7e22ce;font-weight:bold;">{streak_html}</span>'
                f'</div>'
            )
        else:
            html_leader += (
                f'<div class="ticker-badge">'
                f'{dot}'
                f'<span class="ticker-name">{sym}</span>'
                f'{streak_html}'
                f'</div>'
            )

    # Removed leaders
    removed_leaders = [sym for sym in leader_yest if sym not in leader_list]
    for sym in sorted(removed_leaders):
        html_leader += f'<div class="ticker-badge removed-badge">{sym}</div>'

    st.markdown(html_leader, unsafe_allow_html=True)

else:
    st.info("No active setups discovered.")

st.write("")
# if not leader_hist.empty:
#     st.bar_chart(
#         data=leader_hist,
#         x="Date",
#         y="Leader Count",
#         use_container_width=True
#     )

if not leader_hist.empty:
    # 1. Create a temporary copy to prevent altering your original global dataframe
    chart_df = leader_hist.copy()
    
    # 2. Determine if the most recent row (today) holds the absolute maximum value
    today_value = chart_df["Leader Count"].iloc[-1]
    max_value = chart_df["Leader Count"].max()
    min_value = chart_df["Leader Count"].min()
    
    # 3. Add a explicit 'Bar_Color' column to your dataframe
    if today_value == max_value or today_value == min_value:
        # Define base color array, then override the last row (today) with your accent color
        chart_df["Bar_Color"] = "#29B5E8"
        chart_df.iloc[-1, chart_df.columns.get_loc("Bar_Color")] = "#FF4B4B"
    else:
        # Standard uniform blue color if today isn't the highest
        chart_df["Bar_Color"] = "#29B5E8"

    # 4. Render chart mapping color directly to the new dataframe column
    st.bar_chart(
        data=chart_df,
        x="Date",
        y="Leader Count",
        color="Bar_Color",  # Direct Streamlit to read colors line-by-line from this column
        use_container_width=True
    )

# ==========================================
# THEMATIC AI ANALYSIS - RS LEADERS
# ==========================================
def build_leader_industry_map(leader_list, industries_dict):
    """Map each RS leader ticker to its industry group(s)."""
    industry_counts = {}
    ticker_industry = {}
    
    for ticker in leader_list:
        found = []
        for industry, tickers in industries_dict.items():
            if ticker in tickers:
                found.append(industry)
                industry_counts[industry] = industry_counts.get(industry, 0) + 1
        ticker_industry[ticker] = found if found else ["Uncategorized"]
    
    return industry_counts, ticker_industry

def generate_leader_ai_analysis(leader_list, industry_counts, ticker_industry, rs_nh_list, quad_points=None):
    """Call Gemini to summarize RS leader industry concentration."""
    api_key = st.secrets.get("GEMINI_API_KEY")
    if not api_key:
        st.error("🔑 Missing `GEMINI_API_KEY` in Streamlit secrets.")
        return None

    try:
        client = genai.Client(api_key=api_key)

        # Sort industries by leader count descending
        sorted_industries = sorted(industry_counts.items(), key=lambda x: -x[1])
        top_industries_str = "\n".join(
            f"  - {ind}: {cnt} leader(s)" for ind, cnt in sorted_industries[:10]
        )

        # Tag blue dot (RS new high) tickers
        tagged_leaders = []
        for t in leader_list:
            tag = " [BLUE DOT]" if t in rs_nh_list else ""
            inds = ", ".join(ticker_industry.get(t, ["?"]))
            tagged_leaders.append(f"{t}{tag} ({inds})")

        leaders_str = "\n".join(tagged_leaders[:40])

        quad_summary = ""
        if quad_points:
            strong    = [p["industry"] for p in quad_points if p["weekly_rs"] >= 50 and p["monthly_rs"] >= 50]
            improving = [p["industry"] for p in quad_points if p["weekly_rs"] >= 50 and p["monthly_rs"] <  50]
            weakening = [p["industry"] for p in quad_points if p["weekly_rs"] <  50 and p["monthly_rs"] >= 50]
            weak      = [p["industry"] for p in quad_points if p["weekly_rs"] <  50 and p["monthly_rs"] <  50]
            quad_summary = f"""
        Industry RS Quadrant Map (Weekly vs Monthly):
        - Strong (high weekly AND monthly RS, {len(strong)}): {', '.join(strong[:10])}
        - Improving (high weekly, low monthly — rising, {len(improving)}): {', '.join(improving[:10])}
        - Weakening (low weekly, high monthly — fading, {len(weakening)}): {', '.join(weakening[:10])}
        - Weak (low both, {len(weak)}): {', '.join(weak[:10])}
        """

        prompt = f"""
You are a concise IBD-style market analyst. I will give you a list of RS Leader stocks, their industry groups, and the industry RS quadrant map.

RS Leaders ({len(leader_list)} total):
{leaders_str}

Industry concentration (by leader count):
{top_industries_str}

{quad_summary}

Note: [BLUE DOT] = stock hitting a 250-day RS high right now (strongest near-term momentum).

In 4-5 SHORT bullet points:
1. Which 2-3 industries dominate the RS leader list and what does that signal?
2. Are the BLUE DOT stocks concentrated in any particular theme?
3. Any notable divergence or rotation worth flagging?
4. One sentence of insight from the quadrant map — which quadrant has the most concentration, and what does the Strong vs Improving vs Weakening split suggest about market rotation right now?
5. One-line tactical takeaway for a swing trader.

Be direct, use industry names, no fluff.
"""

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        return response.text

    except Exception as e:
        return f"AI analysis error: {str(e)}"


# ==========================================
# UI - RS LEADER AI ANALYSIS
# ==========================================
#st.write("---")
#st.subheader("🤖 RS Leader Industry Analysis")

if not leader_list:
    st.info("No RS leaders found — run the screener first.")
else:
    industry_counts, ticker_industry = build_leader_industry_map(leader_list, INDUSTRIES)
    
    sorted_inds = sorted(industry_counts.items(), key=lambda x: -x[1])
    summary_rows = [{"Industry": ind, "Leaders": cnt} for ind, cnt in sorted_inds]
    
    col_tbl, col_metrics, col_spacer = st.columns([2, 1, 6])
    with col_tbl:
        st.dataframe(
            pd.DataFrame(summary_rows),
            use_container_width=False,
            width=300,
            hide_index=True,
            height=min(300, 36 * len(summary_rows) + 38),
            column_config={
                "Leaders": st.column_config.Column(
                    alignment="left"
                )
            }
        )
    with col_metrics:
        st.metric("Total Leaders", len(leader_list))
        st.metric("Blue Dots", len([s for s in leader_rs_nh_matches if s != 'SPY']))
        st.metric("Industries", len(industry_counts))

    # Auto-run Gemini only when leader list changes
    leader_list_key = str(sorted(leader_list))

    force_rerun = st.button("🔄 Retry AI Analysis", key="retry_leader_ai")

    if force_rerun or st.session_state.get("leader_ai_key") != leader_list_key:
        with st.spinner("Analyzing RS leader concentration via Gemini..."):
            analysis_result = timed(
                "generate_leader_ai_analysis",
                generate_leader_ai_analysis,
                leader_list,
                industry_counts,
                ticker_industry,
                leader_rs_nh_matches,
                quad_points
            )
        if analysis_result:
            st.session_state["leader_ai_result"] = analysis_result
            st.session_state["leader_ai_key"] = leader_list_key

    if "leader_ai_result" in st.session_state:
        st.markdown(st.session_state["leader_ai_result"])

#st.markdown("<br>", unsafe_allow_html=True) # Spacer
st.markdown("---")

# ── RS NEW HIGH BEFORE PRICE ─────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def compute_rs_nh_b4_price(stocks_list, ticker_dfs, benchmark_df_input):
    """
    Pine Script port of rs_nh_b4_price:
    RS is at a 20-bar high BUT price high is NOT yet at its 20-bar high.
    Signals RS leading price — early breakout precursor.
    """
    today_matches = []
    yest_matches  = []

    for ticker in stocks_list:
        try:
            df = ticker_dfs.get(ticker)
            if df is None or len(df) < 25:
                continue

            close_s = df['Close']
            high_s  = df['High']

            # Align with benchmark
            rs = close_s / benchmark_df_input['Close']
            rs = rs.dropna()
            if len(rs) < 22:
                continue

            sma50_s  = close_s.rolling(50).mean()
            sma200_s = close_s.rolling(200).mean()

            # ── TODAY (idx = -1) ──────────────────────────────────────────
            rs_20h    = rs.rolling(20).max()
            price_20h = high_s.rolling(20).max()

            rs_today      = rs.iloc[-1]
            rs_20h_today  = rs_20h.iloc[-1]
            ph_20h_today  = price_20h.iloc[-1]
            h_today       = high_s.iloc[-1]
            c_today       = close_s.iloc[-1]
            sma50_today   = sma50_s.iloc[-1]
            sma200_today  = sma200_s.iloc[-1]

            cond_today = (
                (not pd.isna(rs_20h_today)) and
                (rs_today == rs_20h_today) and
                (h_today < ph_20h_today) and
                (c_today >= 20) and
                (c_today >= sma200_today or c_today >= sma50_today)
            )
            if cond_today:
                today_matches.append(ticker)

            # ── YESTERDAY (idx = -2) ─────────────────────────────────────
            rs_yest     = rs.iloc[-2]
            rs_20h_yest = rs_20h.iloc[-2]
            ph_20h_yest = price_20h.iloc[-2]
            h_yest      = high_s.iloc[-2]
            c_yest      = close_s.iloc[-2]
            sma50_yest  = sma50_s.iloc[-2]
            sma200_yest = sma200_s.iloc[-2]

            cond_yest = (
                (not pd.isna(rs_20h_yest)) and
                (rs_yest == rs_20h_yest) and
                (h_yest < ph_20h_yest) and
                (c_yest >= 20) and
                (c_yest >= sma200_yest or c_yest >= sma50_yest)
            )
            if cond_yest:
                yest_matches.append(ticker)

        except Exception:
            continue

    return sorted(today_matches), sorted(yest_matches)


with st.spinner("Scanning RS New High Before Price..."):
    rs_nh_b4_today, rs_nh_b4_yest = timed(
        "compute_rs_nh_b4_price",
        compute_rs_nh_b4_price,
        stocks_tuple, ticker_dfs_shared, benchmark_df_shared
    )

# st.markdown("---")
st.markdown(f"#### 🔵 RS NH B4 Price = Opportunity ({len(rs_nh_b4_today)})")

if rs_nh_b4_today or rs_nh_b4_yest:
    html_rsnh = ""
    for sym in rs_nh_b4_today:
        #cls = "new-pattern-badge" if sym not in rs_nh_b4_yest else ""
        #html_rsnh += f'<div class="ticker-badge {cls}">{sym}</div>'
        html_rsnh += setup_badge(sym, is_new=(sym not in rs_nh_b4_yest))

    removed_rsnh = [sym for sym in rs_nh_b4_yest if sym not in rs_nh_b4_today]
    for sym in removed_rsnh:
        html_rsnh += f'<div class="ticker-badge removed-badge">{sym}</div>'

    st.markdown(html_rsnh, unsafe_allow_html=True)
else:
    st.info("No active setups discovered.")

st.markdown("---")

# --- 2. TIGHT PPP (Full Horizontal Row Below Two Botak) ---
st.markdown(f"#### 📉 PPP = Opportunity ({len(ppp_list)})")

if ppp_list or ppp_yest:
    # ── Badge row ─────────────────────────────────────────────────────────
    html_p = ""
    for sym in ppp_list:
        #cls = "new-pattern-badge" if sym not in ppp_yest else ""
        #html_p += f'<div class="ticker-badge {cls}">{sym}</div>'
        html_p += setup_badge(sym, is_new=(sym not in ppp_yest))

    removed_ppp = [sym for sym in ppp_yest if sym not in ppp_list]
    for sym in sorted(removed_ppp):
        html_p += f'<div class="ticker-badge removed-badge">{sym}</div>'

    st.markdown(html_p, unsafe_allow_html=True)

    # ── All charts together, 3 per row ────────────────────────────────────
    if ppp_list and show_ppp_charts:
        st.write("")
        CHARTS_PER_ROW = 4
        CHART_SIZE     = 280   # square: width == height

        for row_start in range(0, len(ppp_list), CHARTS_PER_ROW):
            row_tickers = ppp_list[row_start : row_start + CHARTS_PER_ROW]
            cols = st.columns(CHARTS_PER_ROW)

            for col_idx, sym in enumerate(row_tickers):
                with cols[col_idx]:
                    ohlcv_json = get_ppp_ohlcv_json(sym)
                    chart_id   = f"ppp_{sym}_{row_start}_{col_idx}"

                    chart_html = f"""
<div style="font-family:'JetBrains Mono','Fira Code',monospace;">
  <div style="position:relative;width:{CHART_SIZE + 60}px;height:{CHART_SIZE}px;
              border:1px solid #30363d;border-radius:6px;background:#0d1117;">
    <div id="{chart_id}"
         style="width:{CHART_SIZE + 60}px;height:{CHART_SIZE}px;">
    </div>
    <div style="
      position:absolute;top:8px;left:8px;
      font-size:20px;font-weight:900;
      color:rgba(255,255,255,0.15);
      letter-spacing:0.05em;
      pointer-events:none;
      z-index:999;
      user-select:none;
      white-space:nowrap;">
      {sym}
    </div>
  </div>
</div>

<script src="https://unpkg.com/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js"></script>
<script>
(function(){{
  var ohlcv = {ohlcv_json};
  var el = document.getElementById('{chart_id}');
  if (!ohlcv || ohlcv.length === 0) {{
    el.innerHTML = '<p style="color:#7d8590;padding:12px;font-size:11px;">No data.</p>';
    return;
  }}

  var chart = LightweightCharts.createChart(el, {{
    width:  {CHART_SIZE},
    height: {CHART_SIZE},
    layout: {{
      background: {{ type:'solid', color:'#0d1117' }},
      textColor:  '#c9d1d9',
    }},
    grid: {{
      vertLines: {{ color:'#21262d', style:1 }},
      horzLines: {{ color:'#21262d', style:1 }},
    }},
    crosshair: {{
      mode: LightweightCharts.CrosshairMode.Normal,
      vertLine: {{ color:'#58a6ff', width:1, style:1, labelBackgroundColor:'#1f6feb' }},
      horzLine: {{ color:'#58a6ff', width:1, style:1, labelBackgroundColor:'#1f6feb' }},
    }},
    rightPriceScale: {{ borderColor:'#30363d', textColor:'#8b949e' }},
    timeScale: {{
      borderColor:'#30363d', textColor:'#8b949e',
      timeVisible:true, secondsVisible:false,
      fixLeftEdge:true, fixRightEdge:true,
    }},
  }});

  var candles = chart.addCandlestickSeries({{
    upColor:'#26a641',   downColor:'#f85149',
    borderUpColor:'#26a641', borderDownColor:'#f85149',
    wickUpColor:'#26a641',   wickDownColor:'#f85149',
  }});
  candles.setData(ohlcv);

  function calcEMA(data, span) {{
    var k = 2/(span+1), ema = data[0].close, out = [];
    for (var i=0;i<data.length;i++) {{
      ema = data[i].close*k + ema*(1-k);
      if (i >= span-1) out.push({{time:data[i].time, value:parseFloat(ema.toFixed(4))}});
    }}
    return out;
  }}

  function calcSMA(data, period) {{
    var out = [];
    for (var i=period-1;i<data.length;i++) {{
      var s=0; for(var j=i-period+1;j<=i;j++) s+=data[j].close;
      out.push({{time:data[i].time, value:parseFloat((s/period).toFixed(4))}});
    }}
    return out;
  }}

  chart.addLineSeries({{color:'#e3b341',lineWidth:1,
    priceLineVisible:false,lastValueVisible:false}})
    .setData(calcEMA(ohlcv,21));

  chart.addLineSeries({{color:'#58a6ff',lineWidth:1,
    priceLineVisible:false,lastValueVisible:false}})
    .setData(calcSMA(ohlcv,50));

  chart.timeScale().fitContent();

  new ResizeObserver(function(entries){{
    for(var e of entries){{
      chart.applyOptions({{width:e.contentRect.width}});
    }}
  }}).observe(el);
}})();
</script>
"""
                    import streamlit.components.v1 as components
                    components.html(chart_html, height=CHART_SIZE + 32, scrolling=False)

else:
    st.info("No active setups discovered.")

#st.markdown("<br>", unsafe_allow_html=True) # Spacer
st.markdown("---")

# --- GAPPER SECTION ---
st.markdown(f"#### 🚀 Gapper Earning Drift = Opportunity ({len(gapper_list)})")

if gapper_list or gapper_yest:
    # ── Badge row ─────────────────────────────────────────────────────────
    html_g = ""
    for sym in gapper_list:
        #cls = "new-pattern-badge" if sym not in gapper_yest else ""
        #html_g += f'<div class="ticker-badge {cls}">{sym}</div>'
        html_g += setup_badge(sym, is_new=(sym not in gapper_yest))

    removed_gapper = [sym for sym in gapper_yest if sym not in gapper_list]
    for sym in sorted(removed_gapper):
        html_g += f'<div class="ticker-badge removed-badge">{sym}</div>'

    st.markdown(html_g, unsafe_allow_html=True)

    # ── All charts together, 5 per row ────────────────────────────────────
    if gapper_list and show_gap_charts:
        st.write("")
        GAPPER_CHARTS_PER_ROW = 4
        GAPPER_CHART_SIZE     = 280

        for row_start in range(0, len(gapper_list), GAPPER_CHARTS_PER_ROW):
            row_tickers = gapper_list[row_start : row_start + GAPPER_CHARTS_PER_ROW]
            cols = st.columns(GAPPER_CHARTS_PER_ROW)

            for col_idx, sym in enumerate(row_tickers):
                with cols[col_idx]:
                    ohlcv_json = get_gapper_ohlcv_json(sym)
                    chart_id   = f"gapper_{sym}_{row_start}_{col_idx}"
                    _levels        = gapper_gap_levels.get(sym, {})
                    gap_floor_js   = str(_levels["floor"])   if _levels else "null"
                    gap_ceiling_js = str(_levels["ceiling"]) if _levels else "null"
                    gap_date_js    = f'"{_levels["date"]}"'  if _levels else "null"

                    chart_html = f"""
<div style="font-family:'JetBrains Mono','Fira Code',monospace;">
  <div style="position:relative;width:{GAPPER_CHART_SIZE+60}px;height:{GAPPER_CHART_SIZE}px;
              border:1px solid #30363d;border-radius:6px;background:#0d1117;">
    <div id="{chart_id}"
         style="width:{GAPPER_CHART_SIZE+60}px;height:{GAPPER_CHART_SIZE}px;">
    </div>
    <div style="
      position:absolute;top:10%;left:50%;
      transform:translate(-50%,-50%);
      font-size:48px;font-weight:900;
      color:rgba(255,255,255,0.08);
      letter-spacing:0.05em;
      pointer-events:none;
      z-index:999;
      user-select:none;
      white-space:nowrap;">
      {sym}
    </div>
  </div>
</div>

<script src="https://unpkg.com/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js"></script>
<script>
(function(){{
  var ohlcv = {ohlcv_json};
  var el = document.getElementById('{chart_id}');
  if (!ohlcv || ohlcv.length === 0) {{
    el.innerHTML = '<p style="color:#7d8590;padding:12px;font-size:11px;">No data.</p>';
    return;
  }}

  var chart = LightweightCharts.createChart(el, {{
    width:  {GAPPER_CHART_SIZE},
    height: {GAPPER_CHART_SIZE},
    layout: {{
      background: {{ type:'solid', color:'#0d1117' }},
      textColor:  '#c9d1d9',
    }},
    grid: {{
      vertLines: {{ color:'#21262d', style:1 }},
      horzLines: {{ color:'#21262d', style:1 }},
    }},
    crosshair: {{
      mode: LightweightCharts.CrosshairMode.Normal,
      vertLine: {{ color:'#58a6ff', width:1, style:1, labelBackgroundColor:'#1f6feb' }},
      horzLine: {{ color:'#58a6ff', width:1, style:1, labelBackgroundColor:'#1f6feb' }},
    }},
    rightPriceScale: {{ borderColor:'#30363d', textColor:'#8b949e' }},
    timeScale: {{
      borderColor:'#30363d', textColor:'#8b949e',
      timeVisible:true, secondsVisible:false,
      fixLeftEdge:true, fixRightEdge:true,
    }},
  }});

  var gapBottom = {gap_floor_js};
  var gapTop    = {gap_ceiling_js};

if (gapBottom !== null && gapTop !== null && {gap_date_js} !== null) {{
    var gapStartDate = {gap_date_js};
    var t1 = ohlcv[ohlcv.length - 1].time;

    // Upper boundary — fills grey DOWN from gapTop
    var upperArea = chart.addAreaSeries({{
      topColor:    'rgba(160,160,160,0.20)',
      bottomColor: 'rgba(160,160,160,0.20)',
      lineColor:   'rgba(160,160,160,0.55)',
      lineWidth:   1,
      priceLineVisible:       false,
      lastValueVisible:       false,
      crosshairMarkerVisible: false,
    }});
    upperArea.setData([
      {{ time: gapStartDate, value: gapTop }},
      {{ time: t1,           value: gapTop }},
    ]);

    // Lower boundary — fills solid background DOWN from gapBottom to erase bleed
    var lowerArea = chart.addAreaSeries({{
      topColor:    '#0d1117',
      bottomColor: '#0d1117',
      lineColor:   'rgba(160,160,160,0.55)',
      lineWidth:   1,
      priceLineVisible:       false,
      lastValueVisible:       false,
      crosshairMarkerVisible: false,
    }});
    lowerArea.setData([
      {{ time: gapStartDate, value: gapBottom }},
      {{ time: t1,           value: gapBottom }},
    ]);
  }}  

  var candles = chart.addCandlestickSeries({{
    upColor:'#26a641',   downColor:'#f85149',
    borderUpColor:'#26a641', borderDownColor:'#f85149',
    wickUpColor:'#26a641',   wickDownColor:'#f85149',
  }});
  candles.setData(ohlcv);

  function calcEMA(data, span) {{
    var k = 2/(span+1), ema = data[0].close, out = [];
    for (var i=0;i<data.length;i++) {{
      ema = data[i].close*k + ema*(1-k);
      if (i >= span-1) out.push({{time:data[i].time, value:parseFloat(ema.toFixed(4))}});
    }}
    return out;
  }}

  function calcSMA(data, period) {{
    var out = [];
    for (var i=period-1;i<data.length;i++) {{
      var s=0; for(var j=i-period+1;j<=i;j++) s+=data[j].close;
      out.push({{time:data[i].time, value:parseFloat((s/period).toFixed(4))}});
    }}
    return out;
  }}

  chart.addLineSeries({{color:'#e3b341',lineWidth:1,
    priceLineVisible:false,lastValueVisible:false}})
    .setData(calcEMA(ohlcv,21));

  chart.addLineSeries({{color:'#58a6ff',lineWidth:1,
    priceLineVisible:false,lastValueVisible:false}})
    .setData(calcSMA(ohlcv,50));

  chart.timeScale().fitContent();

  new ResizeObserver(function(entries){{
    for(var e of entries){{
      chart.applyOptions({{width:e.contentRect.width}});
    }}
  }}).observe(el);
}})();
</script>
"""
                    import streamlit.components.v1 as components
                    components.html(chart_html, height=GAPPER_CHART_SIZE + 32, scrolling=False)

else:
    st.info("No active setups discovered.")

st.markdown("---")
#st.write(f"inside check: {len(ticker_dfs_shared)}")

with st.spinner("Scanning for Two Botak History..."):
    two_botak_hist= timed("compute_two_botak_history",     compute_two_botak_history,     stocks_tuple, ticker_dfs_shared)

#st.write(f"two_botak_hist shape: {two_botak_hist.shape}")

# --- 1. TWO BOTAK (Full Horizontal Row) ---
st.markdown(f"#### 🔥 Two Botak = Short term Group burst ({len(b_list)})")
if b_list or b_yest:
    html_b = ""
    for sym in b_list:
        #cls = "new-pattern-badge" if sym not in b_yest else ""
        #html_b += f'<div class="ticker-badge {cls}">{sym}</div>'
        html_b += setup_badge(sym, is_new=(sym not in b_yest))
    
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
# if not two_botak_hist.empty:
#     #st.markdown("#### 📊 Two Botak Breadth (60 Days)")
#     st.bar_chart(
#         data=two_botak_hist,
#         x="Date",
#         y="Two Botak Count",
#         use_container_width=True
#     )

# st.write(two_botak_hist.shape, two_botak_hist.head(2))  # remove after confirming
# st.write(f"ticker_dfs_shared keys count: {len(ticker_dfs_shared)}")
# st.write(f"sample keys: {list(ticker_dfs_shared.keys())[:5]}")

if not two_botak_hist.empty:
    # 1. Create a temporary copy to prevent altering your original dataframe
    chart_df = two_botak_hist.copy()
    
    # 2. Determine if the most recent row (today) holds the absolute maximum value
    today_value = chart_df["Two Botak Count"].iloc[-1]
    max_value = chart_df["Two Botak Count"].max()
    
    # 3. Add an explicit 'Bar_Color' column to your dataframe
    if today_value == max_value:
        # Define base color, then override the last row (today) with your accent color
        chart_df["Bar_Color"] = "#29B5E8"
        chart_df.iloc[-1, chart_df.columns.get_loc("Bar_Color")] = "#FF4B4B"
    else:
        # Standard uniform blue color if today isn't the highest
        chart_df["Bar_Color"] = "#29B5E8"

    # 4. Render chart mapping color directly to the new dataframe column
    st.bar_chart(
        data=chart_df,
        x="Date",
        y="Two Botak Count",
        color="Bar_Color",  # Direct Streamlit to read colors line-by-line from this column
        use_container_width=True
    )

st.markdown("---")

with st.spinner("Scanning for Bullish Engulfing History..."):
    engulf_hist   = timed("compute_engulfing_history",     compute_engulfing_history,     stocks_tuple, ticker_dfs_shared)

# --- 3. BULLISH ENGULFING (Full Horizontal Row Below Tight PPP) ---
total_engulf = len(e2_list) + len(e3_list)
st.markdown(f"#### 🐳 Engulfing = HL ({total_engulf})")

if e2_list or e3_list or e2_yest or e3_yest:
    if e2_list or e2_yest:
        st.markdown(f"**2x Engulfing ({len(e2_list)}):**")
        html_e2 = ""
        for sym in e2_list:
            #cls = "new-pattern-badge" if sym not in e2_yest else ""
            #html_e2 += f'<div class="ticker-badge {cls}">{sym}</div>'
            html_e2 += setup_badge(sym, is_new=(sym not in e2_yest))
        
        # Process and append removed 2x engulfing stocks
        removed_e2 = [sym for sym in e2_yest if sym not in e2_list]
        for sym in sorted(removed_e2):
            html_e2 += f'<div class="ticker-badge removed-badge">{sym}</div>'
            
        st.markdown(html_e2, unsafe_allow_html=True)
    
    # st.write("")
    # if len(e3_list) == 0 and len(e3_yest) == 0:
    #     st.markdown("**3x Engulfing Conditions Matched (0):**")
    #     #st.text("None") # Optional: explicit visual feedback for an empty scanner
    # if e3_list or e3_yest:
    #     st.markdown(f"<div style='margin-top:10px;'><b>3x Engulfing Conditions Matched ({len(e3_list)}):</b></div>", unsafe_allow_html=True)
    #     html_e3 = ""
    #     for sym in e3_list:
    #         cls = "new-pattern-badge" if sym not in e3_yest else ""
    #         html_e3 += f'<div class="ticker-badge {cls}">{sym}</div>'
            
    #     # Process and append removed 3x engulfing stocks
    #     removed_e3 = [sym for sym in e3_yest if sym not in e3_list]
    #     for sym in sorted(removed_e3):
    #         html_e3 += f'<div class="ticker-badge removed-badge">{sym}</div>'
            
    #     st.markdown(html_e3, unsafe_allow_html=True)
else:
    st.info("No active setups discovered.")

st.write("")
# if not engulf_hist.empty:
#     #st.markdown("#### 🐳 2x Engulfing Breadth (60 Days)")
#     st.bar_chart(engulf_hist, x="Date", y="2x Engulfing Count", use_container_width=True)

#     #st.markdown("#### 🐳 3x Engulfing Breadth (60 Days)")
#     st.bar_chart(engulf_hist, x="Date", y="3x Engulfing Count", use_container_width=True)

if not engulf_hist.empty:
    # --- 1. 2x Engulfing Chart ---
    chart_df_2x = engulf_hist.copy()
    today_2x = chart_df_2x["2x Engulfing Count"].iloc[-1]
    max_2x = chart_df_2x["2x Engulfing Count"].max()
    
    if today_2x == max_2x:
        chart_df_2x["Bar_Color"] = "#29B5E8"
        chart_df_2x.iloc[-1, chart_df_2x.columns.get_loc("Bar_Color")] = "#FF4B4B"
    else:
        chart_df_2x["Bar_Color"] = "#29B5E8"

    # st.markdown("#### 🐳 2x Engulfing Breadth (60 Days)")
    st.bar_chart(
        data=chart_df_2x,
        x="Date",
        y="2x Engulfing Count",
        color="Bar_Color",
        use_container_width=True
    )

if e3_list or e3_yest:
    st.write("")
    if len(e3_list) == 0 and len(e3_yest) == 0:
        st.markdown("**3x Engulfing (0):**")
        #st.text("None") # Optional: explicit visual feedback for an empty scanner
    elif e3_list or e3_yest:
        st.markdown(f"<div style='margin-top:10px;'><b>3x Engulfing ({len(e3_list)}):</b></div>", unsafe_allow_html=True)
        html_e3 = ""
        for sym in e3_list:
            #cls = "new-pattern-badge" if sym not in e3_yest else ""
            #html_e3 += f'<div class="ticker-badge {cls}">{sym}</div>'
            html_e3 += setup_badge(sym, is_new=(sym not in e3_yest))
            
        # Process and append removed 3x engulfing stocks
        removed_e3 = [sym for sym in e3_yest if sym not in e3_list]
        for sym in sorted(removed_e3):
            html_e3 += f'<div class="ticker-badge removed-badge">{sym}</div>'
            
        st.markdown(html_e3, unsafe_allow_html=True)
else:
    #st.info("No active setups discovered.")
    st.markdown("**3x Engulfing (0):**")

if not engulf_hist.empty:
    # --- 2. 3x Engulfing Chart ---
    chart_df_3x = engulf_hist.copy()
    today_3x = chart_df_3x["3x Engulfing Count"].iloc[-1]
    max_3x = chart_df_3x["3x Engulfing Count"].max()
    
    if today_3x == max_3x:
        chart_df_3x["Bar_Color"] = "#29B5E8"
        chart_df_3x.iloc[-1, chart_df_3x.columns.get_loc("Bar_Color")] = "#FF4B4B"
    else:
        chart_df_3x["Bar_Color"] = "#29B5E8"

    # st.markdown("#### 🐳 3x Engulfing Breadth (60 Days)")
    st.bar_chart(
        data=chart_df_3x,
        x="Date",
        y="3x Engulfing Count",
        color="Bar_Color",
        use_container_width=True
    )

# --- EXTRA TREND METRICS (Stacked Horizontally Below Patterns) ---
#st.markdown("---")
#st.markdown("### 📊 Extra Trend Metrics (PowerTrend Indicators)")
#st.markdown("<br>", unsafe_allow_html=True) # Spacer

st.markdown("---")

with st.spinner("Scanning for PowerTrend History..."):
    powertrend_hist=timed("compute_powertrend_history",    compute_powertrend_history,    stocks_tuple, ticker_dfs_shared)

# --- 4. POWERTREND (Full Horizontal Row) ---
st.markdown(f"#### ⚡ PowerTrend = Thematic Extended ({len(pt_list)})")
if pt_list or pt_yest:
    html_pt = ""
    for sym in pt_list:
        cls = "new-pattern-badge" if sym not in pt_yest else ""
        # Get close price from shared ticker data
        pt_price = ""
        ticker_df_pt = ticker_dfs_shared.get(sym)
        if ticker_df_pt is not None and not ticker_df_pt.empty:
            pt_close = ticker_df_pt['Close'].iloc[-1]
            pt_high  = ticker_df_pt['High'].iloc[-1]
            if not pd.isna(pt_close) and not pd.isna(pt_high):
                pt_price = (
                    f'<span style="color:#aaaaaa; font-size:10px; margin-left:4px;">'
                    #f'C${pt_close:.2f} H${pt_high:.2f}'
                    f'</span>'
                )
        #html_pt += f'<div class="ticker-badge {cls}">{sym}{pt_price}</div>'
        html_pt += setup_badge(sym, is_new=(sym not in pt_yest))
    
    # Process and append removed stocks
    removed_pt = [sym for sym in pt_yest if sym not in pt_list]
    for sym in sorted(removed_pt):
        html_pt += f'<div class="ticker-badge removed-badge">{sym}</div>'
        
    st.markdown(html_pt, unsafe_allow_html=True)
else:
    st.info("No active setups discovered.")

st.write("")
# if not powertrend_hist.empty:
#     st.bar_chart(
#         data=powertrend_hist,
#         x="Date",
#         y="PowerTrend Count",
#         use_container_width=True
#     )

if not powertrend_hist.empty:
    # 1. Create a temporary copy to prevent altering your original dataframe
    chart_df = powertrend_hist.copy()
    
    # 2. Determine if the most recent row (today) holds the absolute maximum value
    today_value = chart_df["PowerTrend Count"].iloc[-1]
    max_value = chart_df["PowerTrend Count"].max()
    min_value = chart_df["PowerTrend Count"].min()
    
    # 3. Add an explicit 'Bar_Color' column to your dataframe
    if today_value == max_value or today_value == min_value:
        # Define base color, then override the last row (today) with your accent color
        chart_df["Bar_Color"] = "#29B5E8"
        chart_df.iloc[-1, chart_df.columns.get_loc("Bar_Color")] = "#FF4B4B"
    else:
        # Standard uniform blue color if today isn't the highest
        chart_df["Bar_Color"] = "#29B5E8"

    # 4. Render chart mapping color directly to the new dataframe column
    st.bar_chart(
        data=chart_df,
        x="Date",
        y="PowerTrend Count",
        color="Bar_Color",  # Direct Streamlit to read colors line-by-line from this column
        use_container_width=True
    )

#st.markdown("<br>", unsafe_allow_html=True) # Spacer
st.markdown("---")

# --- 5. POWERTREND NOT EXTENDED (Full Horizontal Row Below PowerTrend) ---
st.markdown(f"#### ⚡ PowerTrend ... Not Extended ({len(ptne_list)})")
if ptne_list:
    html_ptne = ""
    for sym in ptne_list:
        #cls = "new-pattern-badge" if sym not in ptne_yest else ""
        #html_ptne += f'<div class="ticker-badge {cls}">{sym}</div>'
        html_ptne += setup_badge(sym, is_new=(sym not in ptne_yest))
    st.markdown(html_ptne, unsafe_allow_html=True)
else:
    st.info("No active setups discovered.")

#st.markdown("<br>", unsafe_allow_html=True) # Spacer
st.markdown("---")

# --- 6. VALUE TRAP (Full Horizontal Row Below PowerTrend Not Extended) ---
st.markdown(f"#### ⚠️ Value Trap ({len(vt_list)})")
if vt_list or vt_yest:
    html_vt = ""
    for sym in vt_list:
        #cls = "new-pattern-badge" if sym not in vt_yest else ""
        #html_vt += f'<div class="ticker-badge {cls}">{sym}</div>'
        html_vt += setup_badge(sym, is_new=(sym not in vt_yest))
    
    # Process and append removed stocks
    removed_vt = [sym for sym in vt_yest if sym not in vt_list]
    for sym in sorted(removed_vt):
        html_vt += f'<div class="ticker-badge removed-badge">{sym}</div>'
        
    st.markdown(html_vt, unsafe_allow_html=True)
else:
    st.info("No active setups discovered.")


#st.markdown(html_e2, unsafe_allow_html=True)

# # DEBUG ENGULFING
# for sym in e2_list:
#     ticker_df = ticker_dfs_shared.get(sym)
#     if ticker_df is None:
#         continue
#     close_series = ticker_df['Close']
#     open_series  = ticker_df['Open']
#     high_series  = ticker_df['High']
#     low_series   = ticker_df['Low']

#     be_s   = (open_series < low_series.shift(1)) & (close_series > high_series.shift(1))
#     ec_s   = close_series.where(be_s, other=pd.NA)
#     eng1_s = ec_s.shift(1).ffill()
#     eng2_s = ec_s.shift(2).ffill()
#     eng3_s = ec_s.shift(3).ffill()
#     cnt30  = be_s.rolling(30).sum()
#     two_e  = (cnt30 >= 2) & (close_series > 20) & (close_series > eng1_s) & (close_series > eng2_s)

#     with st.expander(f"🔍 Engulf Debug: {sym}"):
#         st.markdown("**Last 5 rows — all variables**")
#         debug_df = pd.DataFrame({
#             "close"  : close_series,
#             "eng1"   : eng1_s,
#             "eng2"   : eng2_s,
#             "cnt30"  : cnt30,
#             "be_s"   : be_s,
#             "two_e"  : two_e,
#             "c>20"   : close_series > 20,
#             "c>eng1" : close_series > eng1_s,
#             "c>eng2" : close_series > eng2_s,
#         }).tail(5)
#         st.dataframe(debug_df, use_container_width=True)
# # END DEBUG ENGULFING

st.markdown("---")

stocks_tuple = tuple(KNOWN_STOCKS)

# Union of every ticker referenced across all industries (for Setup Rank history)
all_industry_tickers = set()
for tickers in INDUSTRIES.values():
    all_industry_tickers.update(tickers)
all_industry_tickers_tuple = tuple(sorted(all_industry_tickers))

@st.cache_data(ttl=3600)
def download_all_industry_stocks_data(stocks_tuple, known_ticker_dfs):
    benchmark_symbol = "^GSPC"
    missing = [t for t in stocks_tuple if t not in known_ticker_dfs]

    ticker_dfs = {t: known_ticker_dfs[t] for t in stocks_tuple if t in known_ticker_dfs}
    benchmark_df = pd.DataFrame({'Close': known_ticker_dfs[benchmark_symbol]['Close']}) \
        if benchmark_symbol in known_ticker_dfs else None

    if missing or benchmark_df is None:
        all_symbols = missing + ([benchmark_symbol] if benchmark_df is None else [])
        raw_data = yf.download(all_symbols, period="9mo", interval="1d", progress=False, auto_adjust=True)

        for ticker in missing:
            try:
                df = pd.DataFrame({
                    'Open':   raw_data['Open'][ticker],
                    'High':   raw_data['High'][ticker],
                    'Low':    raw_data['Low'][ticker],
                    'Close':  raw_data['Close'][ticker],
                    'Volume': raw_data['Volume'][ticker]
                }).dropna()
                if not df.empty:
                    ticker_dfs[ticker] = df
            except Exception:
                continue

        if benchmark_df is None:
            benchmark_df = pd.DataFrame({'Close': raw_data['Close'][benchmark_symbol]}).dropna()

    return ticker_dfs, benchmark_df

ticker_dfs_all_industries, benchmark_df_all_industries = timed(
    "download_all_industry_stocks_data",
    download_all_industry_stocks_data,
    all_industry_tickers_tuple, ticker_dfs_shared
)

with st.spinner("Computing Setup Rank history..."):
    setup_avgrank_hist = timed(
        "compute_setup_avgrank_history",
        compute_setup_avgrank_history,
        all_data, ticker_dfs_all_industries, benchmark_df_all_industries, 90,
        tuple(sorted(global_setup_tickers)), global_setup_ticker_groups
    )

st.markdown(f"#### 📐 Setup Quality")

if not setup_avgrank_hist.empty:
    chart_df_rank = setup_avgrank_hist.copy()
    today_rank = chart_df_rank["Avg Rank"].iloc[-1]
    min_rank = chart_df_rank["Avg Rank"].min()
    min_idx = chart_df_rank["Avg Rank"].idxmin()

    chart_df_rank["Bar_Color"] = "#29B5E8"
    chart_df_rank.loc[min_idx, "Bar_Color"] = "#90EE90"  # overall lowest bar (best rank)

    if today_rank == min_rank:
        chart_df_rank.iloc[-1, chart_df_rank.columns.get_loc("Bar_Color")] = "#FF4B4B"  # today is also the lowest

    st.bar_chart(
        data=chart_df_rank,
        x="Date",
        y="Avg Rank",
        color="Bar_Color",
        use_container_width=True
    )
else:
    st.info("Insufficient data to compute Setup Avg Rank history.")
  
# ── Timing Summary ───────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("#### ⏱ Test Time")

if _timing_log:
    # Separate industry-level rows from top-level function rows
    industry_rows = {k: v for k, v in _timing_log.items() if k.startswith("RS+Cloud")}
    main_rows     = {k: v for k, v in _timing_log.items() if not k.startswith("RS+Cloud")}

    # Top-level functions table
    # timing_records = [{"Function": k, "Time (ms)": f"{v:,.0f}", "Time (s)": f"{v/1000:.2f}"}
    #                   for k, v in sorted(main_rows.items(), key=lambda x: -x[1])]
    timing_records = [{"Function": k, "Time (s)": f"{v/1000:.2f}"}
                      for k, v in main_rows.items()]

    if timing_records:
        st.dataframe(
            pd.DataFrame(timing_records),
            use_container_width=False,
            width=350,
            hide_index=True
        )

    # Industry RS breakdown — collapsed by default
    if industry_rows:
        total_rs_ms = sum(industry_rows.values())
        with st.expander(f"RS+Cloud per industry — {len(industry_rows)} groups, total {total_rs_ms/1000:.2f}s"):
            # industry_records = [
            #     {"Industry": k.replace("RS+Cloud [", "").replace("]", ""),
            #      "Time (ms)": f"{v:,.0f}",
            #      "Time (s)": f"{v/1000:.2f}"}
            #     for k, v in sorted(industry_rows.items(), key=lambda x: -x[1])
            # ]
            industry_records = [
                {"Industry": k.replace("RS+Cloud [", "").replace("]", ""),
                 "Time (s)": f"{v/1000:.2f}"}
                for k, v in industry_rows.items()
            ]
            st.dataframe(
                pd.DataFrame(industry_records),
                use_container_width=False,
                width=350,
                hide_index=True
            )

    total_ms = sum(_timing_log.values())
    st.caption(f"Total measured wall-clock time: **{total_ms/1000:.2f}s** across {len(_timing_log)} tracked calls")

st.markdown("---")


