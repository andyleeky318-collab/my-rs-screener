import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import time
import re
from google import genai
import plotly.graph_objects as go
import streamlit.components.v1 as components
import requests
from bs4 import BeautifulSoup
import datetime
import base64
from zoneinfo import ZoneInfo

GITHUB_API = "https://api.github.com"

def format_unavailable_reasons(failures):
    if not failures:
        return "previous provider unavailable"
    parts = []
    for provider, reason in failures.items():
        clue = (reason or "unknown reason").strip()
        if not clue:
            clue = "unknown reason"
        elif not clue.startswith("No "):
            clue = clue.split("\n", 1)[0].strip()
            if len(clue) > 60:
                clue = clue[:60].rstrip() + "..."
        parts.append(f"{provider} unavailable ({clue})")
    return "; ".join(parts)

_timing_log = {}  # module-level dict, accumulates across all call sites
_latest_bar_dropped = False
_latest_nan_report_log = {}
_latest_nan_tickers = set()   # 🔧 was: _latest_row_has_nan_reported = False
_benchmark_nan_seen = False

def timed(label, fn, *args, **kwargs):
    """Call fn(*args, **kwargs), record elapsed ms in _timing_log, return result."""
    t0 = time.perf_counter()
    result = fn(*args, **kwargs)
    elapsed = (time.perf_counter() - t0) * 1000
    _timing_log[label] = elapsed
    return result

# 1. Setup Streamlit Page
st.set_page_config(page_title="Chrome Sector RS", page_icon="🐱", layout="wide")
#st.title("🐱 Theme Tracker")

# # ── AMD 1-Year OHLC Data Display ─────────────────────────────────────────────
# #@st.cache_data(ttl=3600)
# def load_amd_data():
#     df = yf.download("IHI", period="1y", interval="1d", auto_adjust=False, progress=False)
#     df.columns = [col[0] if isinstance(col, tuple) else col for col in df.columns]
#     df = df[["Open", "High", "Low", "Close", "Adj Close", "Volume"]].dropna()
#     df.index = df.index.strftime("%Y-%m-%d")
#     df = df.rename_axis("Date").reset_index()
#     for col in ["Open", "High", "Low", "Close", "Adj Close"]:
#         df[col] = df[col].round(2)
#     return df

# amd_df = load_amd_data()

# st.markdown("### 📈 IHI — 1 Year Daily OHLC")
# st.dataframe(
#     amd_df,
#     use_container_width=True,
#     hide_index=True,
#     height=400,
#     column_config={
#         "Date":      st.column_config.TextColumn("Date"),
#         "Open":      st.column_config.NumberColumn("Open",      format="$%.2f"),
#         "High":      st.column_config.NumberColumn("High",      format="$%.2f"),
#         "Low":       st.column_config.NumberColumn("Low",       format="$%.2f"),
#         "Close":     st.column_config.NumberColumn("Close",     format="$%.2f"),
#         "Adj Close": st.column_config.NumberColumn("Adj Close", format="$%.2f"),
#         "Volume":    st.column_config.NumberColumn("Volume",    format="%,d"),
#     }
# )
# st.markdown("---")

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
    'Crypto': ['BLOK', 'MSTR', 'CRCL', 'COIN', 'IBIT', 'RIOT'],
    'Nuclear': ['URA', 'NLR', 'CEG', 'CCJ', 'OKLO', 'UUUU', 'SMR', 'LEU'],
    'MAG7': ['MAGS', 'AAPL', 'GOOGL', 'NVDA', 'META', 'MSFT', 'AMZN', 'TSLA'],
    'ETF': ['XLK', 'XLF', 'XLV', 'XLE', 'XLU', 'XLP', 'XLY', 'XLC', 'XLI', 'XLB'],
    'SPACE': ['SPCX', 'UFO', 'VSAT', 'RKLB', 'SATL', 'RDW', 'LUNR', 'BKSY', 'PL', 'IRDM', 'GSAT', 'ASTS', 'NASA', 'FLY', 'SPCE', 'KRMN', 'SIDU'],
    'CATHIE WOOD': ['ARKG', 'ARKK', 'ARKQ', 'ARKW', 'ARKF', 'ARKX'],
    'CHINA': ['FUTU', 'LI', 'KWEB', 'XPEV', 'NIO', 'PDD', 'BIDU', 'JD', 'BABA'],
    'DATA CENTER': ['WGMI', 'CRWV', 'NBIS', 'IREN', 'WULF', 'CORZ', 'CIFR', 'HUT', 'BTDR', 'EQIX'],
    'SOLAR': ['TAN', 'SEDG', 'ENPH', 'FSLR', 'ARRY', 'SHLS', 'CSIQ', 'RUN', 'DQ'],
    'COML SVCS-ADVRTSNG': ['OMC', 'DJT', 'TTD', 'MGNI', 'PUBM'],
    'AEROSPACE/DEFENSE': ['SHLD', 'ITA', 'XAR', 'RTX', 'LMT', 'HON', 'BA', 'NOC'],
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
    'MEDICAL-BIOMED/BTH': ['IBB', 'BNTX', 'AMGN', 'GILD', 'MRNA', 'ILMN', 'SMMT', 'PCVX', 'BMRN', 'TECH', 'ELAN', 'HALO', 'RNA', 'KRYS', 'ADMA', 'BBIO', 'IMVT', 'AXSM', 'CRSP', 'DNLI', 'ALVO', 'APGE', 'DYN', 'RYTM', 'KYMR', 'EWTX', 'PTGX', 'TWST', 'TXG', 'CGON', 'JANX', 'ARWR', 'VERA', 'NVAX', 'CLDX', 'Q'],
    'MEDIA-RADIO/TV': ['FOX', 'SIRI', 'NXST'],
    'TELCOM-SVC-CBL/SAT': ['CMCSA', 'CHTR'],
    'LEISRE-GAMNG/EQUIP': ['BETZ', 'FLUT', 'LVS', 'MGM', 'WYNN', 'CZR', 'BYD', 'RSI', 'DKNG', 'CHDN', 'PENN'],
    'CHEMICALS-FERTILIZERS': ['MOO', 'NTR', 'CTVA', 'CF', 'MOS', 'FMC', 'SMG'],
    'CHEMICALS-BASIC': ['DD', 'ESI', 'AVNT', 'HUN', 'IOSP', 'DOW', 'LYB', 'WLK', 'AVTR', 'CE', 'EMN', 'CC'],
    'CHEMICALS-SPECIALTY': ['LIN', 'ECL', 'APD', 'ALB', 'CBT', 'NEU', 'KWR', 'HWKN', 'MTX', 'TROX', 'OLN', 'FUL', 'WDFC', 'AZZ', 'UFPT'],
    'ENERGY COAL': ['HCC', 'BTU', 'ARLP', 'AMR'],
    'MEDIA-DIVERSIFIED': ['WMG', 'LYV', 'WBD'],
    'COMPTER-NETWRKING': ['ANET', 'CSCO', 'CALX'],
    'COMPTR-DATA STRGE': ['DRAM', 'EWY', 'WDC', 'STX', 'MU', 'SNDK', 'SKHY'],
    'CMP-HRDWRE/PERIP': ['DELL', 'HPQ', 'SMCI', 'HPE', 'ZBRA', 'NATL'],
    'CONTAINERS/PACKAGING': ['SW', 'BALL', 'PKG', 'AVY', 'AMCR', 'OC', 'CCK', 'ATR', 'GPK', 'SLGN', 'SON', 'GEF', 'OI'],
    'OIL&GAS-DRILLING': ['SLB', 'BKR', 'NE', 'VAL', 'HP', 'SDRL'],
    'BLDG-CMENT/CNCRT': ['CRH', 'MLM', 'VMC', 'EXP', 'KNF', 'USLM'],
    'CMPTER-TECH SRVCS': ['PAYX', 'MSCI', 'VRSK', 'TYL', 'GDDY', 'J', 'FDS', 'AKAM', 'DBX', 'EXLS', 'KD', 'MARA', 'EEFT', 'DXC', 'CORZ', 'AVPT', 'ACN', 'CTSH', 'CDW', 'CACI', 'PSN', 'EPAM', 'DOX', 'KBR', 'GLOB', 'NSIT', 'SAIC', 'INOD'],
    'RETAIL-DPRTMNT STRS': ['DDS', 'M', 'KSS'],
    'RETAIL-DISCNT&VARI': ['DG', 'DLTR', 'FIVE', 'OLLI'],
    'RETAIL-DRUG STORES': ['IHF', 'CVS', 'UNH', 'ELV', 'HUM'],
    'UTILITY-ELCTRIC PWR': ['NEE', 'SO', 'CEG', 'DUK', 'AEP', 'SRE', 'D', 'VST', 'PEG', 'PCG', 'EXC', 'XEL', 'ED', 'EIX', 'WEC', 'ETR', 'DTE', 'FE', 'PPL', 'AEE', 'ES', 'CMS', 'NRG', 'CNP', 'LNT', 'EVRG', 'AES', 'PNW', 'OGE', 'IDA', 'POR', 'ORA', 'BKH', 'TXNM', 'NWE', 'MGEE'],
    'ELEC-POWER/EQPMT': ['GRID', 'ETN', 'GEV', 'AME', 'ROK', 'HUBB', 'RRX', 'GNRC', 'AYI', 'BDC', 'ENS', 'FLNC', 'SMR', 'ATKR', 'PBW', 'POWL', 'VICR', 'BE', 'ENVX', 'QS'],
    'TELCOM-FIBR OPTCS': ['XTL', 'FOTO', 'AAOI', 'COHR', 'CIEN', 'FN', 'LITE', 'AXTI'],
    'ELEC-PARTS': ['APH', 'GLW', 'NVT', 'CAMT', 'TEL'],
    'ELEC-SCNTIFIC/MSRNG': ['PH', 'EMR', 'KEYS', 'FTV', 'CGNX', 'NOVT', 'ST', 'NXT', 'ITRI', 'ESE', 'SXI', 'MTRN', 'VPG'],
    'ELEC-SEMICNDCTR EQP': ['EUV', 'KLIC', 'ASML', 'KLAC', 'AMAT', 'LRCX', 'ONTO', 'NVMI', 'TER', 'AEIS', 'MKSI', 'ENTG', 'ACLS', 'AEHR', 'PLAB'],
    'ELEC-CONTRACT MFG': ['CLS', 'SOLS', 'VRT', 'FLEX', 'PLXS', 'JBL', 'SANM', 'TTMI'],
    'ELEC-MISC PRODUCTS': ['OLED', 'LFUS', 'VSH'],
    'WHOLESALE-ELECT': ['SNX', 'ARW', 'AVT', 'REZI', 'GWW', 'FAST', 'FERG', 'GPC', 'POOL', 'AIT', 'WCC', 'MSM', 'UGI'],
    'RETAIL-CNSMR ELEC': ['BBY', 'GME'],
    'CONSUMER PROD-ELEC': ['SN', 'ROKU', 'WHR', 'SPB', 'SONY'],
    'BLDG-HEAVY CONSTR': ['PWR', 'IESC', 'EME', 'FIX', 'ACM', 'TTEK', 'MTZ', 'APG', 'FLR', 'DY', 'STRL', 'ROAD', 'GVA', 'PRIM'],
    'BLDG-RSIDNT/COMML': ['ITB', 'IBP', 'EXPO', 'DHI', 'LEN', 'NVR', 'PHM', 'TOL', 'MTH', 'KBH', 'SKY', 'MHO', 'FTDR', 'GRBK', 'DFH', 'CCS', 'LGIH'],
    'BLDG-MBILE/MFG & RV': ['CVCO', 'PATK'],
    'POLLUTION CONTROL': ['WM', 'RSG', 'CLH', 'CWST'],
    'COMML SVCS-LEASING': ['URI', 'AER', 'UHAL', 'WSC', 'R', 'HRI', 'WD', 'CAR', 'MGRC', 'PRG'],
    'FINANCE-CARD/PMTPR': ['IPAY', 'XYZ', 'AXP', 'SYF', 'AFRM', 'FCFS', 'SLM', 'V', 'MA', 'PYPL', 'GPN', 'CPAY', 'FOUR', 'WEX', 'PAY', 'RELY', 'SOFI'],
    'FINANCE-CONS LOAN': ['RKT', 'OMF', 'ENVA', 'NNI'],
    'FINANCE-CMRCL LOAN': ['OBDC', 'PFSI', 'CACC'],
    'FINANCE-BLANK CHECK': ['BCSF', 'LOCL', 'MNTN', 'MSDL', 'NCDL', 'PSBD', 'RMI', 'SBXD'],
    'FINANCIAL SVC-SPEC': ['BLK', 'SPGI', 'MCO', 'EFX', 'TRU', 'ICLR', 'BAH', 'MEDP', 'CRL', 'FCN', 'MMS', 'CBZ', 'NSP', 'ICFI', 'EVH', 'FA'],
    'WHOLESALE-FOOD': ['SYY', 'USFD'],
    'RETAIL-SPR/MINI MKTS': ['KR', 'SFM', 'ACI', 'TBBB', 'CASY'],
    'FOOD-PACKAGED': ['KHC', 'GIS', 'CAG', 'SMPL', 'MDLZ', 'KDP', 'HSY', 'CPB', 'SJM', 'POST', 'FLO', 'NOMD', 'UTZ'],
    'FOOD-MEAT PRODUCTS': ['TSN', 'HRL'],
    'FOOD-MISC PREP': ['PEP', 'IFF', 'MKC', 'LW', 'INGR', 'DAR', 'BCPC', 'ASH', 'JJSF', 'SXT', 'TR'],
    'FOOD-CONFECTIONERY': ['FRPT', 'BROS'],
    'BLDG-WOOD PRDS': ['UFPI', 'LPX', 'TREX'],
    'UTILITY-GAS DSTRIBTN': ['TRGP', 'CQP', 'ATO', 'NI', 'MDU', 'BIPC', 'SWX', 'NJR', 'OGS', 'SR', 'CPK', 'EE'],
    'RTAIL-HME FRNSHNGS': ['MBC', 'WSM', 'W', 'RH', 'LOVE'],
    'RETL WHSLE BLDG PRDS': ['HD', 'LOW', 'BLDR', 'FND', 'CNM', 'BCC'],
    'MEDCAL-HOSPITALS': ['HCA', 'THC', 'UHS'],
    'MED-LONG-TRM CARE': ['CHE', 'PACS', 'SGRY', 'ARDT', 'ENSG', 'ADUS'],
    'MEDICAL-SERVICES': ['DVA', 'SOLV', 'EHC', 'ACHC', 'RDNT', 'OPCH', 'HIMS', 'GH', 'BTSG', 'CON', 'AZTA', 'TDOC'],
    'LEISURE-LODGING': ['PEJ', 'MAR', 'HLT', 'RCL', 'CCL', 'VIK', 'H', 'NCLH', 'MTN', 'WH', 'CHH', 'RRR', 'TNL', 'VAC'],
    'COSMETICS/PERSNL CRE': ['PG', 'CL', 'KMB', 'KVUE', 'EL', 'CHD', 'CLX', 'ELF', 'IPAR'],
    'SOAP & CLNG PREPARAT': ['REYN', 'ENR'],
    'DVRSIFIED OPRTIONS': ['MMM', 'RLX', 'WMS', 'AWI', 'BRC', 'YETI', 'LCII'],
    'MCHNRY-GEN INDSTRL': ['GE', 'TT', 'CARR', 'JCI', 'IR', 'XYL', 'DOV', 'LII', 'PNR', 'IEX', 'GGG', 'NDSN', 'LECO', 'WWD', 'AAON', 'FLS', 'MIDD', 'MOD', 'WTS', 'BMI', 'ZWS', 'ESAB', 'TKR', 'GTES', 'FELE', 'KAI', 'MWA', 'NPO', 'CXT', 'OII', 'SYM'],
    'CHEMICALS-PAINTS': ['SHW', 'PPG', 'RPM', 'AXTA'],
    'COMPTER SFTWR-SCRITY': ['CIBR', 'FTNT', 'PANW', 'CRWD', 'CHKP', 'RBRK', 'RPD', 'OKTA', 'ZS', 'TENB', 'S', 'QLYS'],
    'COMPTER SFTWR-ENTR': ['IGV', 'FROG', 'TWLO', 'MSFT', 'ORCL', 'CRM', 'IBM', 'NOW', 'ADP', 'DOCN', 'PLTR', 'ADSK', 'ROP', 'TEAM', 'SNOW', 'VEEV', 'HUBS', 'PTC', 'MANH', 'TOST', 'MNDY', 'WDAY', 'SSNC', 'GWRE', 'BSY', 'PEGA', 'QTWO', 'APPF', 'BOX', 'WK', 'U', 'RNG'],
    'COMPTER SFTWR-DSGN': ['ADBE', 'INTU', 'SNPS', 'CDNS', 'IOT', 'DT', 'TRMB', 'WIX'],
    'CMPTER SFTWR-FINCL': ['FICO', 'FIS', 'NU', 'SHOP'],
    'CMP SFTWR-GAMING': ['TTWO', 'RBLX'],
    'CMP SFTWR-DBASE': ['DDOG', 'MDB', 'ORCL', 'ESTC'],
    'COMPTER SFTWR-DSKTP': ['ZM', 'SNAP', 'Z'],
    'CMPTR SFTWR-MDCL': ['APP', 'HQY'],
    'INTERNET-CONTENT': ['NFLX', 'SPOT', 'PINS', 'RDDT', 'MMYT', 'MTCH', 'YELP', 'GRND'],
    'INTRNT-NETWK SLTNS': ['FSLY', 'IT', 'CSGP', 'VRSN', 'UPST', 'BRZE', 'CARG', 'NET', 'VLTO'],
    'INSURANCE-BROKERS': ['AON', 'AJG', 'WTW', 'BRO', 'RYAN', 'CRVL', 'GSHD'],
    'OIL&GAS INTEGRATED': ['USO', 'XOM', 'CVX', 'OXY'],
    'OIL&GAS-U S EXPL PRO': ['XOP', 'COP', 'EOG', 'FANG', 'DVN', 'EQT', 'EXE', 'PR', 'OVV', 'APA', 'CHRD', 'MTDR', 'NFG', 'CNX', 'CRC', 'CRGY', 'AR', 'RRC', 'MUR', 'MGY', 'SM', 'NOG', 'CRK', 'GPOR', 'XPRO'],
    'OIL&GAS-ROYALTY TRUST': ['VNOM', 'HESM', 'BSM'],
    'RETAIL-INTERNET': ['XRT', 'SE', 'AMZN', 'MELI', 'CPNG', 'LULU', 'EBAY', 'CHWY', 'GLBE', 'ETSY', 'ACVA'],
    'FIN-INVEST BNK/BKRS': ['IAI', 'GS', 'SCHW', 'ICE', 'CME', 'IBKR', 'NDAQ', 'TW', 'STT', 'CBOE', 'HOOD', 'LPLA', 'JEF', 'HLI', 'MKTX', 'XP', 'EVR', 'FRHC', 'PJT', 'MC', 'PIPR', 'VIRT', 'LAZ', 'SNEX'],
    'FNCE-INVSMNT MGT': ['BX', 'MS', 'KKR', 'BN', 'APO', 'ARES', 'OWL', 'RJF', 'TROW', 'TPG', 'PFG', 'BAM', 'NTRS', 'CRBG', 'CG', 'MORN', 'ARCC', 'BEN', 'SF', 'HLNE', 'SEIC', 'IVZ', 'STEP', 'FSK', 'AMG', 'CNS', 'MAIN', 'GBDC', 'AB', 'VCTR', 'APAM', 'HTGC', 'IFS', 'FHI', 'GCMG', 'AMP', 'OWL'],
    'FINANC-PBL INV FDEQT': ['TPL', 'BXSL'],
    'INSURANCE-LIFE': ['PRU', 'EQH', 'PRI', 'VOYA', 'JXN', 'LNC', 'BHF', 'PRVA'],
    'BANKS-MONEY CNTR': ['JPM', 'BAC', 'WFC', 'C', 'COF', 'HSBC'],
    'BANKS-FOREIGN': ['UBS', 'BAP'],
    'BANKS-SUPR RGIONAL': ['PNC', 'HBAN', 'RF', 'CFG', 'KEY', 'ZION', 'FITB', 'TFC', 'MTB', 'ALLY', 'WAL'],
    'BANKS-WST/STHWST': ['KBE', 'BOKF', 'ONB', 'TCBI', 'WAFD', 'PRK', 'BKU', 'IBOC', 'BANF', 'UCB', 'AUB', 'FIBK', 'CATY', 'FHB', 'BOH', 'CVBF'],
    'BANKS-SOUTHEAST': ['FNB', 'FBK', 'HOMB', 'OZK', 'ABCB'],
    'BANKS-MIDWEST': ['KRE', 'FFIN', 'UMBF', 'ASB', 'FULT', 'CBU', 'SFNC', 'FRME', 'NBTB', 'CBSH', 'COLB', 'GBCI', 'UBSI', 'HWC', 'TOWN'],
    'BANKS-NORTHEAST': ['IAT', 'FCNCA', 'EWBC', 'FHN', 'CFR', 'PNFP', 'SSB', 'WTFC', 'BPOP', 'PB', 'WU', 'EBC', 'FBP', 'TBBK'],
    'FINANC-SVINGS & LO': ['WBS', 'TFSL', 'WSFS', 'PFS'],
    'MED-MANAGED CARE': ['UNH', 'ELV', 'CI', 'CNC', 'HUM', 'MOH', 'OSCR', 'ALHC'],
    'TRANSPORTATION-SHIP': ['BOAT', 'KEX', 'FRO', 'MATX', 'GLNG', 'STNG', 'TDW', 'INSW', 'SBLK', 'ZIM', 'TNK'],
    'MDCAL-WHLSLE DRG': ['MCK', 'COR', 'CAH', 'HSIC'],
    'MEDICAL-PRODUCTS': ['TMO', 'ABT', 'DHR', 'A', 'IDXX', 'RMD', 'MTD', 'RVTY', 'BRKR', 'QGEN', 'BIO', 'LNTH', 'GKOS', 'BLCO', 'MMSI'],
    'MEDICAL-SYSTEMS/EQP': ['IHI', 'ISRG', 'SYK', 'BSX', 'MDT', 'BDX', 'GEHC', 'EW', 'DXCM', 'STE', 'WST', 'COO', 'ZBH', 'WAT', 'BAX', 'ALGN', 'PODD', 'NTRA', 'TFX', 'PEN', 'INSP', 'INMD'],
    'METAL PROC & FABRICA': ['RBC', 'MLI', 'VMI', 'ROCK'],
    'CMML SVCS-CNSLTNG': ['TNET', 'LOPE', 'CNXC', 'ABM', 'LAUR', 'QXO', 'G'],
    'AUTO MANUFACTURERS': ['TSLA', 'GM', 'F', 'RIVN'],
    'TRNSPRT-EQP MFG': ['OSK', 'HOG', 'WAB', 'TEX', 'TRN', 'ALG'],
    'LEISRE-MVIES & REL': ['DIS', 'LYV', 'FWONA', 'TKO', 'MSGS', 'FUN', 'CNK', 'PRKS', 'MANU', 'BATRA'],
    'INSRNCE-DIVRSIFIED': ['KIE', 'PGR', 'AFL', 'MET', 'ACGL', 'HIG', 'CINF', 'RGA', 'CNA', 'UNM', 'KNSL', 'GL', 'RLI', 'AXS', 'BWIN', 'ACT', 'FG', 'WTM', 'CNO', 'LMND'],
    'OFFICE SUPPLIES MFG': ['HNI', 'MLKN', 'ACCO'],
    'OIL&GAS-TRNSPRT/PIP': ['EPD', 'WMB', 'ET', 'OKE', 'KMI', 'MPLX', 'LNG', 'WES', 'PAA', 'DTM', 'KNTK', 'AM', 'SOBO', 'PAGP', 'DKL'],
    'OIL&GAS-RFING/MKT': ['PSX', 'MPC', 'VLO', 'DINO', 'IEP', 'PBF', 'CVI', 'SUN'],
    'OIL&GAS-FIELD SERVIC': ['HAL', 'WFRD', 'NOV', 'WHD', 'AROC', 'LBRT', 'USAC', 'KGS', 'AESI'],
    'LEISURE-SERVICES': ['CTAS', 'ROL', 'SCI', 'HRB', 'PLNT', 'LTH', 'VVV', 'GHC', 'UNF', 'LRN', 'DRVN', 'STRA'],
    'CONSUMR PROD-SPECI': ['MSA', 'HAS', 'AS', 'MAT', 'THO', 'PII', 'GOLF', 'HAYW', 'SIG'],
    #'CMP SFTWR-SPC-ENTR': ['TTD', 'MGNI', 'PUBM'],
    'MEDICAL-ETHICAL DRGS': ['XBI', 'NVO', 'LLY', 'JNJ', 'ABBV', 'MRK', 'PFE', 'VRTX', 'REGN', 'BMY', 'ZTS', 'ALNY', 'BIIB', 'RPRX', 'UTHR', 'VTRS', 'INCY', 'INSM', 'SRPT', 'NBIX', 'ROIV', 'RGEN', 'VKTX', 'EXEL', 'JAZZ', 'CYTK', 'IONS', 'BHVN', 'RARE', 'CORT', 'MDGL', 'OGN', 'ALKS', 'CRNX', 'TGTX', 'PRGO', 'RVMD', 'HROW'],
    'MINING-GLD/SILVR/GMS': ['NEM', 'RGLD', 'AEM', 'AU', 'WPM', 'KGC', 'AGI', 'EGO', 'OR'],
    'INSRNCE-PRP/CAS/TITL': ['BRK-B','CB', 'TRV', 'ALL', 'AIG', 'ERIE', 'WRB', 'MKL', 'L', 'EG', 'RNR', 'AFG', 'AIZ', 'MTG', 'SIGI', 'THG', 'KMPR', 'HGTY', 'MCY', 'NMIH', 'PLMR', 'SPNT', 'FNF', 'ORI', 'ESNT', 'FAF', 'RDN', 'AGO'],
    'MEDIA-BOOKS': ['WLY', 'SCHL', 'NYT', 'NWS'],
    #'MEDIA-NEWSPAPERS': ['NWS', 'NYT'],
    'PAPER & PAPER PRODUC': ['IP', 'SLVM'],
    'TRANSPORTATION-RAIL': ['IYT', 'UNP', 'CSX', 'NSC', 'GATX'],
    'REAL STATE DVLPMT/OPS': ['CBRE', 'JLL', 'HHH', 'HGV', 'JOE', 'CWK', 'NMRK'],
    'FINANCE-REIT': ['HASI', 'ESBA'],
    'RETAIL-MJR DSC CHNS': ['WMT', 'COST', 'TGT', 'BJ', 'PSMT'],
    'RETAIL/WHLSLE-AUTO': ['CVNA', 'KMX', 'PAG', 'MUSA', 'LAD', 'AN', 'GPI', 'ABG', 'RUSHA'],
    'RETAIL/WSL-AUTO PRT': ['ORLY', 'AZO'],
    'RETAIL-SPECIALTY': ['MUSA', 'CASY', 'HZO', 'COST', 'BJ', 'ARKO', 'WMT', 'PSMT', 'TBBB', 'TGT', 'DKS', 'FIVE', 'BOBS', 'BBW', 'WINA', 'GME', 'MNSO', 'BBY', 'ULTA', 'EVGO', 'BWMX', 'OLLI', 'DLTR', 'RH', 'ASO', 'WSM', 'WOOF', 'DG', 'BBWI', 'SVV', 'SBH', 'BNED', 'ARHS', 'TSCO', 'EYE'],
    'RETAIL-RESTAURANTS': ['MCD', 'SBUX', 'CMG', 'YUM', 'QSR', 'DRI', 'YUMC', 'CAVA', 'DPZ', 'WING', 'TXRH', 'ARMK', 'SHAK', 'SG', 'EAT', 'WEN', 'CAKE', 'PZZA'],
    'TELECOM SVCS-FOREIGN': ['CCOI', 'LBTYA'],
    'TELCOM-INFRASTR': ['ASTS', 'IRDM', 'NOK', 'AMT'],
    'STEEL-PRODUCERS': ['XME', 'SLX', 'NWPX', 'PKX', 'NUE', 'STLD', 'WS', 'RS', 'ASTL', 'CLF', 'GGB', 'CMC', 'RIO', 'TX', 'MTUS', 'MT', 'HCC', 'MSB', 'VALE', 'SID'],
    'TELCOM-CONS PROD': ['MSI', 'GRMN', 'UI'],
    #'TEXTILES': ['AIN', 'CULP', 'UFI'],
    'TOBACCO': ['PM', 'MO'],
    'BLDG-HAND TOOLS': ['SWK', 'SNA'],
    'TRNSPORTATION-TRCK': ['XTN', 'ODFL', 'JBHT', 'XPO', 'SAIA', 'KNX', 'LSTR', 'SNDR', 'ARCB', 'WERN'],
    'MACHINERY-FARM': ['DE', 'CNH', 'TTC', 'AGCO', 'SITE', 'FSS', 'ACA'],
    'MCHNRY-CNSTR/MNG': ['CAT', 'PCAR', 'LGN', 'ICHR', 'UCTT'],
    'UTILITY-WATER SUPPLY': ['AWK', 'WTRG', 'AWR', 'CWT'],
    'TELCOM SVC-WIRLES': ['IYZ', 'TMUS', 'VZ', 'T', 'LBRDA', 'TIGO', 'TDS'],
    'ELEC-SEMICON FBLSS': ['SMH', 'SIMO', 'ARM', 'NVDA', 'AVGO', 'AMD', 'QCOM', 'ADI', 'MRVL', 'NXPI', 'MPWR', 'MCHP', 'ON', 'SWKS', 'QRVO', 'ALAB', 'CRDO', 'MTSI', 'LSCC', 'CRUS', 'PI', 'RMBS', 'SITM', 'ALGM', 'SLAB', 'POWI', 'IPGP', 'SMTC', 'DIOD', 'SYNA', 'AMBA', 'WOLF'],
    'ELEC-SEMICON FNDRY': ['SOXX', 'TSM', 'TXN', 'INTC', 'GFS', 'AMKR', 'TSEM', 'FORM', 'STM', 'UMC'],
    'ROBOTIC': ['BOTZ', 'AMBA', 'ARBE', 'MBLY', 'NOVT', 'HLX', 'JOBY', 'CGNX', 'ZBRA', 'CRNC', 'RR', 'PRCT', 'PTC', 'NDSN', 'HSAI', 'EMR', 'SERV', 'TER', 'IPGP', 'TRMB', 'SYM', 'OUST'],
    'RARE EARTH': ['REMX', 'USAR', 'METC', 'TMC', 'MP', 'MOS', 'CRML', 'NB', 'PPTA', 'UAMY'],
    'QUANTUM': ['WQTM', 'QNT', 'QMCO', 'IONQ', 'QUBT', 'QBTS', 'RGTI', 'BTQ', 'ARQQ', 'INFQ', 'XNDU'],
    'FUEL CELL': ['FCEL', 'BLDP', 'HYDR', 'BE', 'PLUG'],
    'LITHIUM': ['LIT', 'LAC', 'SLI', 'SQM', 'ALB', 'ATLX'],
    'EUROPE': ['ENOR', 'EFNL', 'EWN', 'EWI', 'EWL', 'EDEN', 'EWO', 'EIRL', 'EWK', 'EWG', 'IEUR', 'EPOL', 'IEV', 'EWU', 'EWP', 'EWQ', 'EWD'],
    'BRAZIL': ['GGB', 'ABEV', 'PBR', 'UGP', 'VALE', 'SID', 'SUZ', 'VIV', 'MELI', 'BSBR', 'CSAN', 'ITUB', 'CIG', 'BBD', 'TIMB', 'XP', 'PAGS', 'INTR', 'SBS'],
    'ARGENTINA': ['ARGT', 'YPF', 'PAM', 'TGS', 'TEO', 'LOMA', 'CRESY', 'CEPU', 'BBAR', 'BMA', 'EDN', 'GGAL', 'IRS', 'SUPV'],
    'CANNABIS': ['MJ', 'CNBS', 'GRWG', 'MSOS', 'IIPR', 'CRON', 'HITI', 'SNDL', 'ACB', 'VFF', 'CGC', 'TLRY', 'OGI'],
    'DRONES': ['RDW', 'JOBY', 'UMAC', 'GD', 'TXT', 'ONDS', 'ACHR', 'DPRO', 'LHX', 'ESLT', 'AVAV', 'EH', 'KTOS', 'PRZO', 'RCAT', 'ZENA'],
    'PRECIOUS METAL': ['GLD', 'SLV', 'PPLT', 'GDX', 'SIL', 'RGLD', 'PLTM', 'PALL'],
    'TRAVEL': ['ABNB', 'EXPE', 'BKNG'],
}

# Cleaned Known Stocks List Reference Array
KNOWN_STOCKS = [
    'PALL', 'PLTM', 'IHF', 'ESTC', 'PRU', 'RGEN', 'UBS', 'TRV', 'WEN', 'OKLO', 'IBB', 'Q', 'OUST', 'VPG', 'WOLF', 'NOK', 'HSBC', 'DLTR', 'SKHY', 'RDDT', 'RL', 'CROX', 'LEVI', 'FOTO', 'GNRC', 'KLIC', 'IWM', 'HBMX', 'PWR', 'EUV', 'GRID', 'MAGS', 'SPCX', 'IBM', 'ELV', 'OSCR', 'QNT', 'HYDR', 'ALGM', 'LGN', 'IESC', 'AEHR', 'ACLS', 'MKSI', 'SMTC', 'AMKR', 
    'LSCC', 'DIOD', 'POWI', 'AA', 'ABBV', 'ALAB', 'AMGN', 'APO', 'BOTZ', 'CRCL', 'CRWV', 'D', 'DRAM', 'DUK', 'EEM', 'EWJ', 'EWY', 'EXC', 'FIGR', 
    'GEV', 'GILD', 'GXC', 'JEF', 'KMI', 'KRMN', 'LIN', 'MNST', 'NASA', 'NEM', 'NTR', 'OR', 
    'OWL', 'Q', 'QQQ', 'RNG', 'RKT', 'SCCO', 'SHLD', 'SO', 'SOLS', 'SPMO', 'SPY', 'SPHB', 'TSEM', 'UNP', 'VTV', 
    'VUG', 'WGMI', 'WMB', 'XEL', 'XMAG', 'XYZ', 'ZIM','VICR', 'SLX', 'CBOE', 'SIMO', 'FLEX', 'POWL', 'VLO', 'DOCN', 
    'IYZ', 'LNG', 'AAOI', 'AXTI', 'TSEM', 'USO', 'JNJ', 
    'HP', 'GLD', 'ALB', 'BUG', 'BX', 'DOW', 'VZ', 'REMX', 'GDX', 'SIL', 'VEEV', 'SNDK', 'TLT', 'APH', 'ARM', 'FANG', 
    'NBIS', 'NVT', 'OXY', 'FORM', 'IBIT', 'QTUM', 'IAI', 'KWEB', 'IHI', 'UFO', 'ITA', 'IYT', 'CVS', 'HUM', 'NEE', 
    'HPE', 'PLAB', 'INOD', 'TTMI', 'CCJ', 'BE', 'SLV', 'PICK', 'COPX', 'MAR', 'XAR', 'VSXY', 'GLW', 'ANF', 'AEO', 
    'AEP', 'GH', 'SANM', 'ROK', 'PSN', 'IAT', 'HROW', 'PL', 'AVAV', 'CIEN', 'COHR', 'NU', 'WULF', 'IREN', 'CIFR', 
    'RDW', 'PH', 'LITE', 'ACHR', 'CACI', 'CRS', 'URA', 'NVO', 'NLR', 'ITB', 'EOSE', 'APP', 'RKLB', 'ASTS', 
    'IONQ', 'RMBS', 'RTX', 'NOC', 'LMT', 'HON', 'ONDS', 'CLS', 'LEU', 'VRT', 'VST', 'NRG', 'CEG', 'SMCI', 'CRDO', 
    'SOFI', 'XLP', 'XLE', 'HIMS', 'HOOD', 'GEV', 'XLV', 'HACK', 'XOP', 'CIBR', 'ICLN', 'XLB', 'XLU', 'XLRE', 'IGV', 
    'XLF', 'IPAY', 'XLC', 'XLI', 'KRE', 'XLK', 'CLOU', 'KBE', 'XME', 'XTL', 'JETS', 'SMH', 'XLY', 'XHB', 
    'XBI', 'XRT', 'MJ', 'META', 'MSFT', 'AAPL', 'AMZN', 'GOOGL', 'NVDA', 'TSLA', 'ARKX', 'ARKQ', 'ARKF', 
    'ARKW', 'ARKK', 'ARKG', 'CCL', 'RCL', 'UAL', 'BA', 'DAL', 'NCLH', 'AAL', 'LUV', 'PINS', 'SNAP', 
    'IBKR', 'SCHW', 'JPM', 'MS', 'GS', 'BAC', 'WFC', 'SPGI', 'BLK', 'NDAQ', 'C', 'LI', 'BIDU', 'NIO', 'XPEV', 
    'BABA', 'PDD', 'JD', 'DQ', 'JKS', 'ENPH', 'FSLR', 'TAN', 'SEDG', 'CSIQ', 'SPWR', 'RUN', 'PBW', 'CLX', 'PG', 
    'EL', 'LULU', 'SBUX', 'NKE', 'MELI', 'EBAY', 'FDX', 'UPS', 'SE', 'JMIA', 'ETSY', 'SHOP', 
    'Z', 'OPEN', 'CHWY', 'CVNA', 'BARK', 'GM', 'BLNK', 'QS', 'F', 'RIVN', 'FCEL', 'CHPT', 'LCID', 
    'UPST', 'PYPL', 'AFRM', 'V', 'MA', 'AXP', 'BITO', 'COIN', 'RIOT', 'MARA', 'MSTR',
    'DKNG', 'PENN', 'BETZ', 'REGN', 'VRTX', 'MRK', 'UNH', 'TMO', 'ISRG', 'ABT', 'IDXX', 'TDOC', 'CRSP', 
    'BRK-B', 'ETN', 'CAT', 'U', 'RBLX', 'SKLZ', 'FSLY', 'TRIP', 'EXPE', 'BKNG', 'ABNB', 'DIS', 'WMT', 
    'COST', 'TGT', 'LOW', 'HD', 'DT', 'SNPS', 'CDNS', 'MDB', 'ORCL', 'NOW', 'ADP', 'SNOW', 'DDOG', 
    'FROG', 'ADSK', 'INTU', 'TEAM', 'WDAY', 'CRM', 'PAYC', 'ANET', 'ADBE', 'ACN', 'EPAM', 'ZM', 'TTD', 'TWLO', 
    'DASH', 'APPS', 'DOCU', 'AI', 'AKAM', 'QLYS', 'PANW', 'FTNT', 'CRWD', 'TENB', 'OKTA', 'ZS', 
    'NET', 'S', 'UMC', 'ASML', 'KEYS', 'CRUS', 'AMD', 'AVGO', 'MU', 'KLAC', 'TXN', 'QRVO', 'TSM', 'SWKS', 'AMBA', 
    'STM', 'MCHP', 'ON', 'QCOM', 'SOXX', 'MRVL', 'ADI', 'LRCX', 'AMAT', 'WDC', 'NXPI', 'TER', 'MPWR', 'INTC', 
    'GFS', 'STX', 'A', 'ZBRA', 'ENTG', 'ONTO', 'TRMB', 'BNTX', 'PFE', 'MRNA', 'NVAX', 'FCX', 'CF', 'DRI', 
    'PEP', 'XOM', 'LLY', 'CL', 'MCD', 'KO', 'GE', 'CVX', 'FISV', 'DE', 'WM', 'HLT', 'FUTU', 'UBER', 
    'TIGR', 'EQIX', 'DPZ', 'CSCO', 'COKE', 'SONY', 'FDS', 'MCO', 'GRAB', 'PTON', 'AMT', 'LIT', 'CMG', 'IPO', 
    'INMD', 'NNDM', 'MP', 'FUBO', 'SPOT', 'ALGN', 'PZZA', 'LOVE', 'LMND', 'POOL', 'PLTR', 'ROKU', 
    'CELH', 'NFLX', 'DHI', 'DELL'
]
# Ensure uniqueness
KNOWN_STOCKS = list(set(KNOWN_STOCKS))

#Solely for Deepvue
LIME_STOCKS = [
    'CIBR', 'COPX', 'DRAM', 'GDX', 'IBIT', 'IGV', 'IHI',
    'IPAY', 'ITB', 'JETS', 'KRE', 'KWEB', 'LIT', 'MAGS',
    'PBW', 'REMX', 'SHLD', 'SIL', 'SLX', 'SMH', 'TAN',
    'UFO', 'URA', 'USO', 'VTV', 'VUG', 'WGMI', 'XBI',
    'XME', 'XRT', 'FOTO', 'SPY', 'QQQ', 'RSP'
]

LIME_STOCKS1 = [
    'IHF', 'CIBR', 'COPX', 'DRAM', 'GDX', 'IBIT', 'IGV', 'IHI', 'EWY',
    'IPAY', 'ITB', 'JETS', 'KRE', 'KWEB', 'LIT', 'MAGS',
    'PBW', 'REMX', 'SHLD', 'SIL', 'SLX', 'SMH', 'TAN',
    'UFO', 'URA', 'USO', 'VTV', 'VUG', 'WGMI', 'XBI',
    'XME', 'XRT', 'XTL', 'SPY', 'QQQ', 'RSP', 'FOTO', 'KBE', 'NLR', 
    'CLOU', 'XHB', 'BUG', 'HACK', 'ITA', 'IAT', 'XOP', 'NASA', 
    'XTN', 'IYT', 'BOAT', 'MOO', 'BLOK', 'PICK', 'BOTZ', 'MJ', 'WQTM', 'IBB', 'KIE', 'IAI', 'SOXX'
]

TICKER_ALIASES = {
    "GOOG": "GOOGL",
}

def normalize_ticker(sym):
    """Map alias tickers (e.g. GOOG) to their canonical KNOWN_STOCKS symbol (GOOGL)."""
    if not sym:
        return sym
    sym = sym.strip().upper()
    return TICKER_ALIASES.get(sym, sym)

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
    })#.ffill().dropna()   # <-- was: .dropna()

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

@st.cache_data(ttl=900)
def fetch_etf_daily_direction(etf_symbols):
    if not etf_symbols:
        return {}, {}, None, {}

    finnhub_key = st.secrets.get("FINNHUB_API_KEY")
    if not finnhub_key:
        st.warning("FINNHUB_API_KEY missing from secrets.")
        return {}, {}, None, {}

    changes      = {}
    pct_changes  = {}
    latest_date  = None
    market_caps  = {
        'XLK': 125.3, 'XLF': 51.2, 'XLV': 39.4, 'XLE': 39.1, 'XLI': 31.1,
        'XLC': 23.8, 'XLU': 22.7, 'XLY': 22.4, 'XLP': 14.7, 'XLB': 8.0
    }

    for sym in etf_symbols:
        try:
            resp = requests.get(
                "https://finnhub.io/api/v1/quote",
                params={"symbol": sym, "token": finnhub_key},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("c") is None:
                continue

            changes[sym]     = float(data.get("d") or 0.0)
            pct_changes[sym] = float(data.get("dp") or 0.0)

            ts = data.get("t")
            if ts:
                latest_date = datetime.datetime.fromtimestamp(ts)

        except Exception as e:
            st.warning(f"Finnhub fetch error for {sym}: {e}")
            continue

    return changes, pct_changes, latest_date, market_caps

@st.cache_data(ttl=3600)
def fetch_ratio_chart_data(ratio_pairs, period="1y"):
    symbols = sorted({sym for pair in ratio_pairs for sym in pair})
    if not symbols:
        return pd.DataFrame()

    td_key = st.secrets.get("TWELVEDATA_API_KEY")
    if not td_key:
        st.warning("TWELVEDATA_API_KEY missing from secrets.")
        return pd.DataFrame()

    CHUNK_SIZE = 7  # stay under the 8-credits/minute free-tier ceiling
    chunks = [symbols[i:i + CHUNK_SIZE] for i in range(0, len(symbols), CHUNK_SIZE)]
    all_data = {}

    for i, chunk in enumerate(chunks):
        try:
            resp = requests.get(
                "https://api.twelvedata.com/time_series",
                params={
                    "symbol": ",".join(chunk),
                    "interval": "1day",
                    "outputsize": 260,
                    "apikey": td_key,
                },
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            if len(chunk) == 1:
                data = {chunk[0]: data}
            all_data.update(data)
        except Exception as e:
            st.warning(f"Twelve Data fetch error (chunk {i+1}): {e}")

        if i < len(chunks) - 1:
            time.sleep(61)  # wait for credit quota to reset before next chunk

    close_series_map = {}
    for sym in symbols:
        sym_data = all_data.get(sym)
        if not sym_data or sym_data.get("status") != "ok" or "values" not in sym_data:
            continue
        rows = sym_data["values"]
        s = pd.Series({row["datetime"]: float(row["close"]) for row in rows})
        s.index = pd.to_datetime(s.index)
        close_series_map[sym] = s.sort_index()

    if not close_series_map:
        return pd.DataFrame()

    close_df = pd.DataFrame(close_series_map).dropna(how="all")
    ratio_df = pd.DataFrame(index=close_df.index)
    for numerator, denominator in ratio_pairs:
        if numerator not in close_df.columns or denominator not in close_df.columns:
            continue
        ratio = close_df[numerator].div(close_df[denominator]).replace([np.inf, -np.inf], np.nan).dropna()
        if ratio.empty:
            continue
        ratio_df[f"{numerator}/{denominator}"] = ratio

    return ratio_df.dropna(how="all").tail(60)

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
        new_high_tickers = []
        new_low_tickers = []
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

                # 1. New High / New Low (only include stocks trading above $20)
                if currentClose >= 20 and currentClose >= high_of_52week:
                    breadth_stats['new_high'] += 1
                    new_high_tickers.append(ticker)
                if currentClose >= 20 and currentClose <= low_of_52week:
                    breadth_stats['new_low'] += 1
                    new_low_tickers.append(ticker)

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

        return breadth_stats, stage_counts, total_processed, new_high_tickers, new_low_tickers

    except Exception as e:
        return {}, {1: 0, 2: 0, 3: 0, 4: 0, 0: 0}, 0, []

# ============================================================
# PINE SCRIPT "Relative Strength Table" — 39-ticker RS panel
# Methodology ported from the TradingView Pine indicator:
# percentrank(price_ratio, length) for periods 5/21/63/126,
# sorted by the 21-period RS (Pine default sort_key_options='P2').
# ============================================================
PINE_RS_TICKERS = [
    'QQQ', 'QQQE', 'RSP', 'ITB', 'IWM', 'XLV', 'XLE', 'XLF', 'PBW', 'XLB',
    'XLP', 'XLU', 'XLY', 'XLK', 'XLC', 'XLI', 'FOTO', 'SMH', 'SLV', 'NLR',
    'TAN', 'IBIT', 'JETS', 'GLD', 'COPX', 'UFO', 'KWEB', 'CIBR', 'IGV', 'USO',
    'MAGS', 'ITA', 'IYT', 'IHI', 'XBI', 'LIT', 'WGMI', 'DRAM', 'REMX'
]

@st.cache_data(ttl=3600)
def download_pine_rs_data(tickers_tuple, benchmark_symbol="SPY"):
    all_symbols = list(tickers_tuple) + [benchmark_symbol]
    raw = yf.download(all_symbols, period="9mo", interval="1d", progress=False, auto_adjust=True)
    return raw['Close']


def _percentrank_last(series, length):
    """Pine ta.percentrank(source, length) for the latest bar only."""
    if series is None or len(series) < length + 1:
        return np.nan
    window = series.iloc[-(length + 1):-1].values
    current = series.iloc[-1]
    if len(window) < length:
        return np.nan
    return round(float(np.sum(window < current)) / length * 100, 2)


def _is_latest_close_above_52w_close(close_series):
    """True only when the latest close exceeds the prior 52-week close."""
    if close_series is None:
        return False
    close = pd.Series(close_series).dropna()
    if close.empty or len(close) < 2:
        return False
    latest_close = float(close.iloc[-1])
    prior_closes = close.iloc[-253:-1] if len(close) > 253 else close.iloc[:-1]
    if prior_closes.empty:
        return False
    previous_52w_close = float(prior_closes.max())
    return latest_close > previous_52w_close


@st.cache_data(ttl=3600)
def compute_pine_rs_table(tickers_tuple, benchmark_symbol="SPY"):
    close_data = download_pine_rs_data(tickers_tuple, benchmark_symbol)
    if benchmark_symbol not in close_data.columns:
        return []
    bench_close = close_data[benchmark_symbol].dropna()

    rows = []
    for t in tickers_tuple:
        if t not in close_data.columns:
            continue
        close = close_data[t].dropna()
        aligned_close, aligned_bench = close.align(bench_close, join='inner')
        if aligned_close.empty:
            continue
        ratio = aligned_close / aligned_bench
        rs5   = _percentrank_last(ratio, 5)
        rs21  = _percentrank_last(ratio, 21)
        rs63  = _percentrank_last(ratio, 63)
        rs126 = _percentrank_last(ratio, 126)
        rows.append({
            "Ticker": t,
            "RS5": rs5,
            "RS21": rs21,
            "RS63": rs63,
            "RS126": rs126,
            "Is52WHigh": _is_latest_close_above_52w_close(close),
        })

    # Sort descending by RS(21), tie-broken by RS63 -> RS126 -> RS5
    # (fixes ties like SLV/NLR/GLD/COPX/IGV all at 100% RS21 — the one with
    # stronger RS63/RS126/RS5 should rank higher, matching TradingView)
    def _sort_key(r):
        return (
            r["RS21"]  if not pd.isna(r["RS21"])  else -1,
            r["RS5"]   if not pd.isna(r["RS5"])   else -1,            
            r["RS63"]  if not pd.isna(r["RS63"])  else -1,
            r["RS126"] if not pd.isna(r["RS126"]) else -1,
        )

    rows.sort(key=_sort_key, reverse=True)
    return rows

def render_pine_rs_table_html(rows, max_height):
    if not rows:
        return "<div style='color:#888;font-size:11px;'>No RS data available.</div>"

    sector_etfs = {"XLE", "XLK", "XLY", "XLB", "XLF", "XLI", "XLC", "XLU", "XLV", "XLP"}
    index_etfs  = {"QQQE", "QQQ", "RSP", "IWM", "SMH", "MAGS"}

    def fmt(v):
        return "-" if v is None or pd.isna(v) else f"{v:.2f}%"

    def rs_cell_style(v):
        base = "padding:1px 5px;text-align:right;font-size:9px;border:1px solid #ccc;white-space:nowrap;"
        if v is not None and not pd.isna(v) and v >= 80:
            return base + "background:rgba(255, 183, 197, 0.8);color:#000000;"
        return base + "background:#ffffff;color:#000000;"

    header_html = (
        "<tr>"
        "<th style='padding:1px 5px;background:#ffffff;color:#000000;text-align:left;font-size:9px;border:1px solid #ccc;white-space:nowrap;'></th>"
        "<th style='padding:1px 5px;background:#ffffff;color:#000000;text-align:center;font-size:9px;border:1px solid #ccc;white-space:nowrap;'>RS(5)</th>"
        "<th style='padding:1px 5px;background:#0000ff;color:#ffffff;text-align:center;font-size:9px;border:1px solid #ccc;white-space:nowrap;'>RS(21)*</th>"
        "<th style='padding:1px 5px;background:#ffffff;color:#000000;text-align:center;font-size:9px;border:1px solid #ccc;white-space:nowrap;'>RS(63)</th>"
        "<th style='padding:1px 5px;background:#ffffff;color:#000000;text-align:center;font-size:9px;border:1px solid #ccc;white-space:nowrap;'>RS(126)</th>"
        "</tr>"
    )

    body_html = ""
    n = len(rows)
    for i, r in enumerate(rows):
        sym = r["Ticker"]
        ticker_label = f"{sym}**" if r.get("Is52WHigh", False) else sym
        name_bg, name_color = "#ffffff", "#000000"
        if i == n - 1:
            name_bg, name_color = "#ff0000", "#ffffff"
        if sym in sector_etfs:
            name_bg, name_color = "#00ffff", "#000000"
        if sym in index_etfs:
            name_bg, name_color = "#FFD700", "#ff0000"

        body_html += (
            f"<tr>"
            f"<td style='padding:1px 5px;background:{name_bg};color:{name_color};text-align:left;font-size:9px;border:1px solid #ccc;font-weight:bold;white-space:nowrap;'>{ticker_label}</td>"
            f"<td style='{rs_cell_style(r['RS5'])}'>{fmt(r['RS5'])}</td>"
            f"<td style='{rs_cell_style(r['RS21'])}'>{fmt(r['RS21'])}</td>"
            f"<td style='{rs_cell_style(r['RS63'])}'>{fmt(r['RS63'])}</td>"
            f"<td style='{rs_cell_style(r['RS126'])}'>{fmt(r['RS126'])}</td>"
            f"</tr>"
        )

    return (
        f"<div style='overflow:visible; border:1px solid #333; border-radius:4px; "
        f"width:max-content; margin-left:-25px;'>"
        f"<table style='border-collapse:collapse; background:#ffffff;'>"
        f"<thead>{header_html}</thead><tbody>{body_html}</tbody></table></div>"
    )

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
    new_style_industry_table = st.toggle("Old/New Style", value=True)  # NEW: True = new style (KNOWN_STOCKS only), False = old style (all tickers, unchanged)
    
    if st.button("Refresh Deepvue Theme", use_container_width=True):
        # Clear the caches for BOTH functions so fresh data is requested
        download_lime_stocks_data.clear()
        st.toast("Cache cleared! Fetching real-time market data...", icon="🔄")

    if st.button("Refresh Deepvue Breadth", use_container_width=True):
        # Clear the caches for BOTH functions so fresh data is requested
        compute_breadth_and_stage.clear()
        st.toast("Cache cleared! Fetching real-time market data...", icon="🔄")

    if st.button("Clear Cache"):
        st.cache_data.clear()

# st.markdown("---")
#st.markdown(f"#### 📊 Market Breadth")

lime_ticker_dfs = timed(
    "download_lime_stocks_data",
    download_lime_stocks_data,
    tuple(LIME_STOCKS)
)

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

    lime_perf_rows.append({
        "sym": sym, "pct": pct_1d, "pct_1w": pct_1w, "pct_1m": pct_1m,
        "is_2m_high": bool(c_today >= df_sym['Close'].max())   # NEW
    })

if lime_perf_rows:

    two_month_high_syms = {r["sym"] for r in lime_perf_rows if r.get("is_2m_high")}

    pattern_defs = """
    <defs>
    <pattern id="stripe-blue" width="6" height="6" patternTransform="rotate(45)" patternUnits="userSpaceOnUse">
        <rect width="6" height="6" fill="#9CC4EA"/>
        <line x1="0" y1="0" x2="0" y2="6" stroke="#378ADD" stroke-width="3"/>
    </pattern>
    <pattern id="stripe-pink" width="6" height="6" patternTransform="rotate(45)" patternUnits="userSpaceOnUse">
        <rect width="6" height="6" fill="#FFC2DE"/>
        <line x1="0" y1="0" x2="0" y2="6" stroke="#FF69B4" stroke-width="3"/>
    </pattern>
    </defs>
    """

    BAR_MAX_PX = 175  # was 200

    rows_1d = sorted(lime_perf_rows, key=lambda x: -x["pct"])
    rows_1w = sorted([r for r in lime_perf_rows if r["pct_1w"] is not None], key=lambda x: -x["pct_1w"])
    rows_1m = sorted([r for r in lime_perf_rows if r["pct_1m"] is not None], key=lambda x: -x["pct_1m"])

    max_abs_1d = max(abs(r["pct"])     for r in rows_1d) or 1
    max_abs_1w = max(abs(r["pct_1w"])  for r in rows_1w) or 1
    max_abs_1m = max(abs(r["pct_1m"])  for r in rows_1m) or 1

    ROW_H   = 21   # was 18
    LABEL_W = 120   # was 110
    COL_W   = LABEL_W + BAR_MAX_PX
    GAP     = 55   # was 60
    PADDING = 13    # was 12
    FS      = 13    # font size

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
        col_header(X0_1w, "1 WEEK (Developing)") +
        col_header(X0_1m, "1 MONTH (Leading Theme)")
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

    def draw_col(rows, pct_key, max_abs, col_x, stripe_syms=None):
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
                f'width="{LABEL_W + bw}" height="19" '
                f'fill="transparent" style="cursor:pointer;"/>'
            )
            bar_fill = c
            if stripe_syms and sym in stripe_syms:
                bar_fill = "url(#stripe-blue)" if c == "#378ADD" else "url(#stripe-pink)"
            html += (
                f'<rect class="bar bar-{sym}" data-sym="{sym}" '
                f'x="{col_x + LABEL_W}" y="{y - 4}" '
                f'width="{bw}" height="11" rx="2" fill="{bar_fill}" '
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
            ticker_color = (
                "#FFD700" if sym == "SPY"
                else "#ADFF2F" if sym == "QQQ"
                else "#FFD700" if sym == "RSP"
                else "#cccccc"
            )
            html += (
                f'<text class="lbl lbl-{sym}" data-sym="{sym}" '
                f'x="{col_x + 62}" y="{y + 4}" '  # 4px gap after %
                f'font-size="{FS}" font-family="Source Sans Pro,sans-serif" '
                f'font-weight="600" fill="{ticker_color}" '
                f'text-anchor="start" style="cursor:pointer;">{sym}</text>'
            )
        return html

    cols_html  = draw_col(rows_1d, "pct",    max_abs_1d, X0_1d, stripe_syms=two_month_high_syms)
    cols_html += draw_col(rows_1w, "pct_1w", max_abs_1w, X0_1w, stripe_syms=two_month_high_syms)
    cols_html += draw_col(rows_1m, "pct_1m", max_abs_1m, X0_1m, stripe_syms=two_month_high_syms)

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
        {pattern_defs}
        {headers_html}
        {lines_html}
        {cols_html}
    </svg>
    </div>
    {js}
    """

    col_lime_chart, col_pine_rs = st.columns([4, 1])  # NEW: right-side column for RS table
    with col_lime_chart:
        st.components.v1.html(html_out, height=SVG_H + 24, scrolling=False)
    with col_pine_rs:  # NEW
        pine_rs_rows = timed("compute_pine_rs_table", compute_pine_rs_table, tuple(PINE_RS_TICKERS))
        st.markdown(render_pine_rs_table_html(pine_rs_rows, SVG_H), unsafe_allow_html=True)
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
    breadth_stats, stage_counts, breadth_total, new_high_tickers, new_low_tickers = timed(
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
            f"    <span style='font-size:12px;color:#888888;'>{val:,}</span>"
            f"    <span style='font-size:12px;color:#888888;'>{counterpart:,}</span>"
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
    with st.expander(f"New Highs ({len(new_high_tickers)})", expanded=True):
        if new_high_tickers:
            nh_html = (
                "<div style='display:flex;flex-wrap:wrap;gap:6px;"
                "padding:12px 4px;'>"
            )
            for sym in sorted(new_high_tickers):
                if sym in LIME_STOCKS1:
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

    with st.expander(f"New Lows ({len(new_low_tickers)})", expanded=True):
        if new_low_tickers:
            nl_html = (
                "<div style='display:flex;flex-wrap:wrap;gap:6px;"
                "padding:12px 4px;'>"
            )
            for sym in sorted(new_low_tickers):
                if sym in LIME_STOCKS1:
                    nl_html += (
                        f'<div class="ticker-badge lime-badge">'
                        f'<span style="color:#000;font-weight:bold;">{sym}</span></div>'
                    )
                elif sym in KNOWN_STOCKS:
                    nl_html += (
                        f'<div class="ticker-badge new-pattern-badge">'
                        f'<span style="color:#111;font-weight:bold;">{sym}</span></div>'
                    )
                else:
                    nl_html += f'<div class="ticker-badge">{sym}</div>'
            nl_html += "</div>"
            st.markdown(nl_html, unsafe_allow_html=True)
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

# ── Distribution Chart (after breadth bars) ──────────────────────────────────
@st.cache_data(ttl=3600)
def compute_pct_change_distribution(stocks_list, _ticker_dfs):
    """
    Bucket each stock's daily % change into bands matching the reference image.
    Buckets: ≤-7%, -7~-5%, -5~-3%, -3~0%, 0 (unchanged), 0~3%, 3~5%, 5~7%, ≥7%
    """
    buckets = {
        "≤-7%":   0,
        "-7~-5%": 0,
        "-5~-3%": 0,
        "-3~0%":  0,
        "0":      0,
        "0~3%":   0,
        "3~5%":   0,
        "5~7%":   0,
        "≥7%":    0,
    }

    for ticker in stocks_list:
        df = _ticker_dfs.get(ticker)
        if df is None or len(df) < 2:
            continue
        c_today = df['Close'].iloc[-1]
        c_prev  = df['Close'].iloc[-2]
        if pd.isna(c_today) or pd.isna(c_prev) or c_prev == 0:
            continue

        pct = (c_today - c_prev) / c_prev * 100

        if pct == 0:
            buckets["0"] += 1
        elif pct <= -7:
            buckets["≤-7%"] += 1
        elif pct <= -5:
            buckets["-7~-5%"] += 1
        elif pct <= -3:
            buckets["-5~-3%"] += 1
        elif pct < 0:
            buckets["-3~0%"] += 1
        elif pct < 3:
            buckets["0~3%"] += 1
        elif pct < 5:
            buckets["3~5%"] += 1
        elif pct < 7:
            buckets["5~7%"] += 1
        else:
            buckets["≥7%"] += 1

    return buckets

dist_buckets = timed(
    "compute_pct_change_distribution",
    compute_pct_change_distribution,
    stocks_tuple, ticker_dfs_shared
)

# ── Render Distribution SVG ───────────────────────────────────────────────────
bucket_order = ["≤-7%", "-7~-5%", "-5~-3%", "-3~0%", "0", "0~3%", "3~5%", "5~7%", "≥7%"]
bucket_colors = {
    "≤-7%":   "#FF4B6E",
    "-7~-5%": "#FF4B6E",
    "-5~-3%": "#FF4B6E",
    "-3~0%":  "#FF4B6E",
    "0":      "#888888",
    "0~3%":   "#00C076",
    "3~5%":   "#00C076",
    "5~7%":   "#00C076",
    "≥7%":    "#00C076",
}

vals       = [dist_buckets[b] for b in bucket_order]
max_val    = max(vals) or 1

SVG_W      = 340
SVG_H      = 220
PAD_L      = 15
PAD_R      = 15
PAD_TOP    = 50        # room for count labels above bars
PAD_BOT    = 32        # room for bucket labels below bars
MAX_BAR_H  = SVG_H - PAD_TOP - PAD_BOT   # 138px

n          = len(bucket_order)
slot_w     = (SVG_W - PAD_L - PAD_R) / n
bar_w      = slot_w * 0.52

bars_svg   = ""
labels_svg = ""
counts_svg = ""

for i, (label, val) in enumerate(zip(bucket_order, vals)):
    cx     = PAD_L + slot_w * i + slot_w / 2
    bar_h  = max(int(val / max_val * MAX_BAR_H), 3)
    bar_x  = cx - bar_w / 2
    bar_y  = PAD_TOP + (MAX_BAR_H - bar_h)
    color  = bucket_colors[label]

    # Bar
    bars_svg += (
        f'<rect x="{bar_x:.1f}" y="{bar_y}" '
        f'width="{bar_w:.1f}" height="{bar_h}" '
        f'rx="3" fill="{color}"/>'
    )

    # Count label above bar
    count_y = bar_y - 6
    counts_svg += (
        f'<text x="{cx:.1f}" y="{count_y}" '
        f'text-anchor="middle" font-size="9" '
        f'font-family="Source Sans Pro,sans-serif" '
        f'font-weight="700" fill="{color}">{val:,}</text>'
    )

    # Bucket label below
    label_y = SVG_H - 6
    display_label = "" if label == "0" else label
    labels_svg += (
        f'<text x="{cx:.1f}" y="{label_y}" '
        f'text-anchor="middle" font-size="8" '
        f'font-family="Source Sans Pro,sans-serif" '
        f'fill="#888888">{display_label}</text>'
    )

# Baseline
baseline_y = PAD_TOP + MAX_BAR_H
baseline_svg = (
    f'<line x1="{PAD_L}" y1="{baseline_y}" '
    f'x2="{SVG_W - PAD_R}" y2="{baseline_y}" '
    f'stroke="#444444" stroke-width="0.8"/>'
)

dist_html = f"""
<div style="background:#0e1117; border-radius:6px; padding:8px 0 0; max-width:408px;">
  <svg xmlns="http://www.w3.org/2000/svg"
       viewBox="0 0 {SVG_W} {SVG_H}"
       width="100%" height="auto"
       style="display:block;">
    {baseline_svg}
    {bars_svg}
    {counts_svg}
    {labels_svg}
  </svg>
</div>
"""

st.markdown(dist_html, unsafe_allow_html=True)

left_tail  = dist_buckets["≤-7%"] + dist_buckets["-7~-5%"]
right_tail = dist_buckets["≥7%"] + dist_buckets["5~7%"]
avg_bucket = sum(dist_buckets.values()) / len(dist_buckets)

if left_tail > avg_bucket * 3:
    st.markdown("⚠️ **Fat left tail — distribution day**", unsafe_allow_html=True)
elif right_tail > avg_bucket * 3:
    st.markdown("🚀 **Fat right tail — thrust day**", unsafe_allow_html=True)

st.markdown("---")

st.write("")
st.write("")

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Ma+Shan+Zheng&display=swap');
    .calligraphy-banner {
        text-align: center;
        padding: 40px 0 60px;
    }
    .calligraphy-banner span {
        font-family: 'Ma Shan Zheng', cursive;
        font-size: 90px;
        color: #e0d8c3;
        letter-spacing: 18px;
        text-shadow: 0 0 12px rgba(224, 216, 195, 0.15);
    }
    </style>
    <div class="calligraphy-banner">
        <span>顺势而为</span>
    </div>
    """,
    unsafe_allow_html=True
)

st.markdown("---")

# 4. IMPLEMENTATION OF NEW NORMALIZED RS METHOD AND EMA CLOUD
@st.cache_data(ttl=3600)
def get_rs_and_cloud_data_cached(tickers_tuple, benchmark_ticker, length, _benchmark_df):
    tickers = list(tickers_tuple)
    try:
        #all_tickers = tickers + [benchmark_ticker]
        #data = yf.download(all_tickers, period="2y", interval="1d", progress=False, auto_adjust=True)
        data = yf.download(tickers, period="2y", interval="1d", progress=False, auto_adjust=True)

        close_data = data['Close']
        high_data = data['High']
        low_data = data['Low']
        open_data = data['Open']

        close_data = close_data.copy()
        close_data[benchmark_ticker] = _benchmark_df['Close'].reindex(close_data.index)#.ffill()

        global _latest_bar_dropped, _latest_nan_tickers, _benchmark_nan_seen  # 🔧

        last_row_nan_mask = close_data.iloc[-1].isna()
        latest_row_nan_pct = last_row_nan_mask.mean()

        benchmark_last_is_nan = (
            pd.isna(close_data[benchmark_ticker].iloc[-1])
            if benchmark_ticker in close_data.columns else False
        )

        # 🔧 FIX: accumulate into a shared, deduped set across ALL industry groups.
        # Only record actual STOCK tickers (exclude the benchmark symbol itself
        # from the "missing tickers" list — that's tracked separately).
        if latest_row_nan_pct > 0:
            nan_cols = [c for c in last_row_nan_mask[last_row_nan_mask].index.tolist() if c != benchmark_ticker]
            _latest_nan_tickers.update(nan_cols)
            if benchmark_last_is_nan:
                _benchmark_nan_seen = True

        if latest_row_nan_pct > 0:
            close_data.iloc[-1] = close_data.iloc[-1].fillna(close_data.iloc[-2])
            high_data.iloc[-1]  = high_data.iloc[-1].fillna(high_data.iloc[-2])
            low_data.iloc[-1]   = low_data.iloc[-1].fillna(low_data.iloc[-2])
            open_data.iloc[-1]  = open_data.iloc[-1].fillna(open_data.iloc[-2])
            _latest_bar_dropped = True
        else:
            _latest_bar_dropped = False

        # st.sidebar.write("After fill — benchmark tail(3):", close_data[benchmark_ticker].tail(3).tolist())
        # for t in tickers:
        #     if t in close_data.columns:
        #         st.sidebar.write(f"After fill — {t} tail(3): {close_data[t].tail(3).tolist()}")

        # st.sidebar.write("latest_row_nan_pct:", latest_row_nan_pct)
        # st.sidebar.write("_latest_bar_dropped:", _latest_bar_dropped)
        # st.sidebar.write("Per-ticker NaN on last row:", close_data.iloc[-1][tickers].isna().to_dict())
        
        valid_tickers = [t for t in tickers if t in close_data.columns and close_data[t].notna().sum() >= length]

        # st.sidebar.write("valid_tickers:", valid_tickers)
        # for t in tickers:
        #     if t in close_data.columns:
        #         st.sidebar.write(f"  {t}: notna count = {close_data[t].notna().sum()} (need >= {length})")
        #     else:
        #         st.sidebar.write(f"  {t}: NOT in close_data.columns at all")

        if not valid_tickers: return None, None, None, {}, None, None, None, None, None

        # --- New RS Logic ---
        bench_close = close_data[benchmark_ticker]

        # st.sidebar.write("benchmark tail(5):", bench_close.tail(5).tolist())
        # st.sidebar.write("benchmark NaN count:", bench_close.isna().sum())

        stock_scores = {}
        stock_scores_prev = {}
        stock_scores_1m = {}
        stock_scores_3d = {}
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

            # st.sidebar.write(
            #     f"{ticker}: rs={current_rs}, hh={current_hh}, ll={current_ll}, "
            #     f"hh_isna={pd.isna(current_hh)}, ll_isna={pd.isna(current_ll)}, "
            #     f"hh==ll: {current_hh == current_ll if pd.notna(current_hh) and pd.notna(current_ll) else 'n/a'}"
            # )
            # # Also check the raw rolling window itself, not just the last value:
            # st.sidebar.write(f"  {ticker} rs_ratio tail(5): {rs_ratio_series.tail(5).tolist()}")
            # st.sidebar.write(f"  {ticker} hh tail(5): {hh.tail(5).tolist()}")
            # st.sidebar.write(f"  {ticker} ll tail(5): {ll.tail(5).tolist()}")

            # Get values from 1 week ago (5 trading days ago)
            prev_rs = rs_ratio_series.iloc[-6]
            prev_hh = hh.iloc[-6]
            prev_ll = ll.iloc[-6]

            # Get values from 1 month ago (21 trading days ago)
            m1_rs = rs_ratio_series.iloc[-22]
            m1_hh = hh.iloc[-22]
            m1_ll = ll.iloc[-22]

            # Get values from 3 trading days ago (for ROC acceleration adjustment)
            d3_rs = rs_ratio_series.iloc[-4]
            d3_hh = hh.iloc[-4]
            d3_ll = ll.iloc[-4]
            
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

            if pd.isna(d3_hh) or pd.isna(d3_ll) or d3_hh == d3_ll:
                total_score_3d = 0
            else:
                total_score_3d = int(((99 - 1) * (d3_rs - d3_ll) / (d3_hh - d3_ll)) + 1)

            # This will now store a clean whole number (e.g., 85 instead of 85.34)
            stock_scores[ticker] = total_score

            #st.sidebar.write(f"  {ticker} total_score = {total_score}, current_price = {price_lookup.get(ticker)}")

            stock_scores_prev[ticker] = total_score_prev
            stock_scores_1m[ticker] = total_score_1m
            stock_scores_3d[ticker] = total_score_3d

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

            cond1 = (adrPercent.iloc[-1] >= 2.45) and (adrPercent.iloc[-1] < 8.05)

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

            # if ticker == "AMD" and _latest_bar_dropped:
            #     st.sidebar.warning("⚠️ DEBUGGING FOR AMD ACTIVATED")
                
            #     # Check metrics availability
            #     debug_info = {
            #         "Ticker Symbol": ticker,
            #         "Current Cached Price": round(current_price, 2) if 'current_price' in locals() else "N/A",
            #         "Total Raw RS Score": total_score,
            #         "Has Data Available": ticker in close_data.columns,
            #         "Historical Bars Fetched": int(close_data[ticker].notna().sum()),
            #         "Requested Window Length": length,
            #         "Is Current High NaN": pd.isna(current_hh),
            #         "Is Current Low NaN": pd.isna(current_ll)
            #     }
            #     st.sidebar.json(debug_info)            

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
        rs_perf_3d_raw = pd.Series(stock_scores_3d).astype(int)
        
        # Build a list of tickers that strictly have a price greater than 20
        valid_price_tickers = [ticker for ticker, price in price_lookup.items() if price > 20]

        # st.sidebar.write("price_lookup:", price_lookup)
        # st.sidebar.write("valid_price_tickers (>$20):", valid_price_tickers)
        # st.sidebar.write("rs_perf before price filter:", rs_perf_raw.to_dict())
        # st.sidebar.write("rs_perf after price filter:", rs_perf.to_dict())
        
        # Filter the series so only stocks with a price > 20 remain
        rs_perf = rs_perf_raw[rs_perf_raw.index.isin(valid_price_tickers)]
        rs_perf_prev = rs_perf_prev_raw[rs_perf_prev_raw.index.isin(valid_price_tickers)]
        rs_perf_1m = rs_perf_1m_raw[rs_perf_1m_raw.index.isin(valid_price_tickers)]
        rs_perf_3d = rs_perf_3d_raw[rs_perf_3d_raw.index.isin(valid_price_tickers)]
        
        return rs_perf, rs_perf, cloud_tickers, price_lookup, rs_perf_prev, rs_perf_1m, rs_perf_3d, cloud_21ema_tickers, cloud_wick_tickers, ma50_bounce_tickers
    except Exception as e:
        st.error(f"Error: {e}")
        return None, None, None, {}, None, None, None, None, None, None

with st.sidebar:
    if st.button("Refresh Table", use_container_width=True):
        get_rs_and_cloud_data_cached.clear()
        st.toast("Industry RS cache cleared! Reloading table...", icon="📊")

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

                    atr_mult_s = None
                    if atr_pct is not None and sma50_series is not None:
                        pct_gain_s  = ((close_series - sma50_series) / sma50_series) * 100
                        atr_mult2_s = pct_gain_s / atr_pct.replace(0, 0.001)
                        atr_mult_s  = (atr_mult2_s * 10).fillna(0).astype(int) / 10

                    if bool(pt_s.iloc[-1]):
                        atr_val_pt = round(float(atr_mult_s.iloc[-1]), 1) if atr_mult_s is not None and pd.notna(atr_mult_s.iloc[-1]) else None
                        powertrend_matches.append((ticker, atr_val_pt))
                    if bool(pt_s.iloc[-2]): powertrend_yest.append(ticker)

                    if atr_mult_s is not None:
                        ptne_s = pt_s & (atr_mult_s <= 4)

                        if bool(ptne_s.iloc[-1]):
                            atr_val_ptne = round(float(atr_mult_s.iloc[-1]), 1) if pd.notna(atr_mult_s.iloc[-1]) else None
                            powertrend_ne_matches.append((ticker, atr_val_ptne))
                        if bool(ptne_s.iloc[-2]): powertrend_ne_yest.append(ticker)

                # --- Value Trap ---
                if atr_pct is not None and sma50_series is not None and df_len >= 50:
                    pct_gain_vt  = ((close_series - sma50_series) / sma50_series) * 100
                    atr_mult2_vt = pct_gain_vt / atr_pct.replace(0, 0.001)
                    atr_mult2_vt = atr_mult2_vt.replace([float('inf'), -float('inf')], pd.NA)
                    atr_mult_vt  = (atr_mult2_vt.fillna(0) * 10).astype(int) / 10
                    vt_s = (atr_mult_vt < -4) & (close_series >= 20)

                    if bool(vt_s.iloc[-1]):
                        atr_value = round(float(atr_mult_vt.iloc[-1]), 1) if pd.notna(atr_mult_vt.iloc[-1]) else None
                        value_trap_matches.append((ticker, atr_value))
                    if bool(vt_s.iloc[-2]): value_trap_yest.append(ticker)

                # --- PPP ---
                if df_len >= 200 and sma50_series is not None and sma200_series is not None and atr_pct is not None:
                    hl_ratio_ppp = high_series / low_series
                    adr_ppp = 100 * (hl_ratio_ppp.rolling(20).mean() - 1)
                    adr_ok = (adr_ppp.iloc[-1] >= 2.45) and (adr_ppp.iloc[-1] < 8.05)

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
    perf, rs_scores, cloud_list, price_lookup, rs_scores_prev, rs_scores_1m, rs_scores_3d, cloud_21ema_list, cloud_wick_list, ma50_bounce_list = timed(
        f"RS+Cloud [{industry_name}]",
        get_rs_and_cloud_data_cached,
        tuple(tickers), benchmark, 90, benchmark_df_shared   # ← added benchmark_df_shared
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

        if rs_scores_3d is not None and not rs_scores_3d.empty:
            top_n_scores_3d = rs_scores_3d.nlargest(int(top_n))
            group_avg_3d = top_n_scores_3d.mean()
        else:
            group_avg_3d = group_avg

        df_tickers = pd.DataFrame({"Ticker": rs_scores.index, "RS Score": rs_scores.values}).sort_values(by="RS Score", ascending=False)
        all_data.append({
            "Industry": industry_name, 
            "Group RS": group_avg, 
            "Group RS Prev": group_avg_prev, 
            "Group RS 1M": group_avg_1m, 
            "Group RS 3D": group_avg_3d,
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

with st.sidebar.expander(f"⚠️ NaN-today report ({len(_latest_nan_tickers)} tickers)", expanded=False):
    st.write("benchmark_last_is_nan:", _benchmark_nan_seen)
    st.write(f"Tickers missing today's data: {len(_latest_nan_tickers)}")
    st.write(sorted(_latest_nan_tickers))

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

def setup_badge(sym, is_new=False, is_removed=False, extra_prefix="", extra_suffix="", extra_suffix_color="#888888", extra_style="", extra_text_color=None):
    """Render a ticker badge, colored by setup-category precedence:
    50ma_bounce (orange) > 21ema_wick (aqua) > 21ema_cloud (purple) > new (gold) > default.
    extra_text_color: if given, overrides just the ticker-name text color."""
    suffix_html = f'<span style="margin-left:4px; color:{extra_suffix_color}; font-weight:bold;"> {extra_suffix}</span>' if extra_suffix else ""
    if is_removed:
        return f'<div class="ticker-badge removed-badge" style="{extra_style}">{extra_prefix}{sym}{suffix_html}</div>'
    if sym in ma50bounce_all:
        return (f'<div class="ticker-badge orange-badge" style="{extra_style}">{extra_prefix}'
                f'<span style="color:#111111;font-weight:bold;">{sym}</span>{suffix_html}</div>')
    if sym in cloudwick_all:
        return (f'<div class="ticker-badge aqua-badge" style="{extra_style}">{extra_prefix}'
                f'<span style="color:#000000;font-weight:bold;">{sym}</span>{suffix_html}</div>')
    if sym in cloud21ema_all:
        return (f'<div class="ticker-badge purple-badge" style="{extra_style}">{extra_prefix}'
                f'<span style="color:#000000;font-weight:bold;">{sym}</span>{suffix_html}</div>')
    if is_new:
        text_color = extra_text_color or "#111111"
        return (f'<div class="ticker-badge new-pattern-badge" style="{extra_style}">{extra_prefix}'
                f'<span style="color:{text_color};font-weight:bold;">{sym}</span>{suffix_html}</div>')
    text_color = extra_text_color or "#eeeeee"
    return (f'<div class="ticker-badge" style="{extra_style}">{extra_prefix}'
            f'<span style="color:{text_color};font-weight:bold;">{sym}</span>{suffix_html}</div>')

@st.cache_data(ttl=3600)
def compute_industry_vol_flags(industries_dict, _ticker_dfs):
    """
    For each industry, count how many tickers meet highVolCount >= 6 OR volScore >= 3.5.
    Returns:
      - flagged_industries: set of industry names where at least 2 tickers meet the condition.
      - industry_vol_tickers: dict of industry -> list of qualifying tickers (only for flagged industries).
    """
    flagged_industries = set()
    industry_vol_tickers = {}

    for industry, tickers in industries_dict.items():
        qualifying_tickers = []

        for ticker in tickers:
            try:
                df = _ticker_dfs.get(ticker)
                if df is None or len(df) < 22:
                    continue

                high  = df['High']
                low   = df['Low']

                daily_range = 100 * (high / low - 1)
                avg_range   = daily_range.rolling(20).mean()
                std_range   = daily_range.rolling(20).std(ddof=1)

                z_series    = (daily_range - avg_range) / std_range.replace(0, float('nan'))

                # highVolDay = z > 1.5
                high_vol_day = (z_series > 1.5).astype(int)

                # highVolCount = sum of highVolDay over last 20 bars
                high_vol_count = high_vol_day.rolling(20).sum().iloc[-1]

                # volScore = sum of max(z - 1.5, 0) over last 20 bars
                vol_score = (z_series - 1.5).clip(lower=0).rolling(20).sum().iloc[-1]

                if pd.isna(high_vol_count) or pd.isna(vol_score):
                    continue

                if high_vol_count >= 6 or vol_score >= 3.5:
                    qualifying_tickers.append(ticker)

            except Exception:
                continue

        if len(qualifying_tickers) >= 2:
            flagged_industries.add(industry)
            industry_vol_tickers[industry] = qualifying_tickers

    return flagged_industries, industry_vol_tickers

with st.spinner("Computing industry volatility flags..."):
    vol_flagged_industries, industry_vol_tickers = timed(
        "compute_industry_vol_flags",
        compute_industry_vol_flags,
        INDUSTRIES, ticker_dfs_shared
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

def generate_top_industries_theme_insight(
    df_main_sorted, all_data_list, top_n_industries=20,
    new_high_tickers=None, new_low_tickers=None
):
    """
    Standalone (no external function deps) — summarizes what theme/sector
    rotation is dominating the top-N industries by Group RS right now.
    Optionally also folds in New High / New Low tickers to flag any
    common industry/theme/subgroup driving those lists.
    Same provider fallback chain as generate_leader_ai_analysis, kept
    self-contained so it can be called anywhere in the script.
    """
    if df_main_sorted is None or df_main_sorted.empty:
        return None

    top_rows = df_main_sorted.head(top_n_industries)

    lines = []
    for _, row in top_rows.iterrows():
        industry = row["Industry"]
        item = next((d for d in all_data_list if d["Industry"] == industry), None)
        top_tickers = ""
        if item is not None:
            known_only = item["Tickers"][item["Tickers"]["Ticker"].isin(KNOWN_STOCKS)]
            top5 = known_only.sort_values("RS Score", ascending=False).head(5)
            top_tickers = ", ".join(f"{t}({s:.0f})" for t, s in zip(top5["Ticker"], top5["RS Score"]))

        rs_1w  = row.get("Group RS Prev", None)
        rs_1m  = row.get("Group RS 1M", None)
        roc    = row.get("ROC", None)

        rs_1w_str = f"{rs_1w:.1f}" if rs_1w is not None else "n/a"
        rs_1m_str = f"{rs_1m:.1f}" if rs_1m is not None else "n/a"
        roc_str   = f"{roc:.1f}"   if roc   is not None else "n/a"

        lines.append(
            f"  {row['Current Rank']}. {industry} — RS {row['Group RS']:.1f} "
            f"(1W: {rs_1w_str}, 1M: {rs_1m_str}, △T: {roc_str}) — top: {top_tickers}"
        )

    industries_block = "\n".join(lines)

    # ── FIXED: New High / New Low industry breakdown — now includes the
    # ACTUAL tickers that triggered NH/NL for each industry, not the
    # unrelated top-5-RS tickers used in the top-20 industries_block. ──
    nh_nl_block = ""
    new_high_tickers = new_high_tickers or []
    new_low_tickers  = new_low_tickers or []

    def _industry_ticker_map(ticker_list, industries_dict):
        """industry -> sorted list of tickers (from ticker_list) that belong to it."""
        _, ticker_industry = build_leader_industry_map(ticker_list, industries_dict)
        industry_map = {}
        for t, inds in ticker_industry.items():
            for ind in inds:
                if ind == "Uncategorized":
                    continue
                industry_map.setdefault(ind, []).append(t)
        for ind in industry_map:
            industry_map[ind] = sorted(set(industry_map[ind]))
        return industry_map

    nh_industry_ticker_map = _industry_ticker_map(new_high_tickers, INDUSTRIES)
    nl_industry_ticker_map = _industry_ticker_map(new_low_tickers, INDUSTRIES)

    nh_sorted = sorted(nh_industry_ticker_map.items(), key=lambda x: -len(x[1]))
    nl_sorted = sorted(nl_industry_ticker_map.items(), key=lambda x: -len(x[1]))

    nh_str = "\n".join(
        f"  - {ind} ({', '.join(tickers)}): {len(tickers)}"
        for ind, tickers in nh_sorted[:10]
    ) or "  - none"
    nl_str = "\n".join(
        f"  - {ind} ({', '.join(tickers)}): {len(tickers)}"
        for ind, tickers in nl_sorted[:10]
    ) or "  - none"

    nh_tickers_str = ", ".join(sorted(new_high_tickers)[:40]) or "none"
    nl_tickers_str = ", ".join(sorted(new_low_tickers)[:40]) or "none"

    if new_high_tickers or new_low_tickers:
        nh_nl_block = f"""
New 52-Week Highs ({len(new_high_tickers)} tickers): {nh_tickers_str}
New High industry concentration (with the EXACT tickers from this New Highs list that belong to each industry):
{nh_str}

New 52-Week Lows ({len(new_low_tickers)} tickers): {nl_tickers_str}
New Low industry concentration (with the EXACT tickers from this New Lows list that belong to each industry):
{nl_str}
"""

    nh_nl_label_block = ""
    if new_high_tickers or new_low_tickers:
        nh_nl_label_block = (
            '**New High/Low Concentration**: Is there a common industry, theme, or subgroup '
            'dominating the New Highs list? Same question for New Lows — is there a clear '
            'industry cluster showing weakness? Note any overlap or contrast between the two.\n'
        )

    prompt = f"""
You are a concise IBD-style market analyst. Below are the top {len(top_rows)} industries right now, ranked by Group Relative Strength, with their strongest tickers.

Each row shows: current RS, RS from 1 week ago, RS from 1 month ago, and △T (a blended thrust/acceleration score combining recent RS momentum). Use these to judge whether an industry's strength is accelerating, decelerating, or newly emerging.

{industries_block}
{nh_nl_block}
IMPORTANT FORMATTING RULE — TWO SEPARATE TICKER SOURCES, DO NOT MIX THEM:
1. When discussing the TOP {len(top_rows)} INDUSTRIES section (Dominant Theme, Sub-Themes, Outliers, Tactical Takeaway), bracket each industry name with its "top:" tickers shown in that section above, e.g. "Aerospace/Defense (LMT, NOC, SHLD, ITA, XAR)".
2. When discussing the NEW HIGH/NEW LOW CONCENTRATION line specifically, bracket each industry name ONLY with the tickers listed next to it under "New High industry concentration" or "New Low industry concentration" above — these are the actual tickers that are currently at a new high/low, and are usually a DIFFERENT set of tickers than that industry's top-RS list. Never reuse the top-industries tickers for the New High/Low line, and never invent tickers not explicitly listed for that industry in the relevant section.

Respond with EXACTLY these lines, each starting with the bolded label below followed by a colon, then the content on the SAME line. Do not add extra bullets, headers, or commentary outside these lines. Do not rename, reorder, or skip a label{"" if nh_nl_label_block else " (omit the New High/Low Concentration line entirely since no data was given)"}.

**Dominant Theme**: What is the dominant market theme or macro narrative connecting these top industries right now (e.g. AI/semis, defense, gold/metals, crypto, industrials, etc)?
**Sub-Themes**: Are there 2-3 distinct sub-themes or clusters visible, rather than one single theme?
**Outliers**: Any industry here that looks like an outlier / doesn't fit the dominant theme?
{nh_nl_label_block}**Tactical Takeaway**: One-line tactical takeaway for a swing trader on where leadership is concentrated (and where weakness is concentrated, if New Lows data was given).

Be direct, name industries explicitly with the bracket format above, no fluff, no repeating the prompt. Each line's content should be 1-2 sentences max.
"""

    TRANSIENT_CODES = ["503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED", "quota",
                        "overloaded", "high demand", "rate_limit", "capacity", "timeout", "502", "529", "404"]
    def is_transient(e):
        return any(c.lower() in e.lower() for c in TRANSIENT_CODES)

    failures = {}

    gemini_attempts = [
        ("Gemini 2.5 Flash", st.secrets.get("GEMINI_API_KEY"),   "gemini-2.5-flash"),
        ("Gemini 3.5 Flash", st.secrets.get("GEMINI_API_KEY_2"), "gemini-3.5-flash"),
    ]
    for gemini_label, gemini_key, gemini_model in gemini_attempts:
        if not gemini_key:
            failures[gemini_label] = "No key in secrets"
            continue
        try:
            from google import genai as google_genai
            client = google_genai.Client(api_key=gemini_key)
            response = client.models.generate_content(model=gemini_model, contents=prompt)
            return f"🟦 **{gemini_label}**\n\n{response.text}"
        except Exception as e:
            err = str(e)
            if not is_transient(err):
                failures[gemini_label] = err[:120]
                continue
            failures[gemini_label] = err[:120]

    groq_key = st.secrets.get("GROQ_API_KEY")
    if groq_key:
        try:
            from openai import OpenAI as OpenAIClient
            groq_client = OpenAIClient(api_key=groq_key, base_url="https://api.groq.com/openai/v1")
            completion = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "system", "content": "You are a concise IBD-style market analyst."},
                          {"role": "user", "content": prompt}],
                max_tokens=400, temperature=0.4,
            )
            summary = format_unavailable_reasons(failures)
            return f"🟧 **Groq / Llama-3.3-70b** *({summary})*\n\n{completion.choices[0].message.content}"
        except Exception as e:
            err = str(e)
            if not is_transient(err):
                return f"🔴 **Groq error (non-transient)**\n\n{err}"
            failures["Groq"] = err[:120]
    else:
        failures["Groq"] = "No GROQ_API_KEY"

    openrouter_key = st.secrets.get("OPENROUTER_API_KEY")
    if openrouter_key:
        try:
            from openai import OpenAI as OpenAIClient
            or_client = OpenAIClient(
                api_key=openrouter_key, base_url="https://openrouter.ai/api/v1",
                default_headers={"HTTP-Referer": "https://your-app-name.streamlit.app", "X-Title": "Theme Tracker"},
            )
            completion = or_client.chat.completions.create(
                model="meta-llama/llama-3.1-8b-instruct:free",
                messages=[{"role": "system", "content": "You are a concise IBD-style market analyst."},
                          {"role": "user", "content": prompt}],
                max_tokens=400, temperature=0.4,
            )
            summary = format_unavailable_reasons(failures)
            return f"🟣 **OpenRouter / Llama-3.1-8b** *({summary})*\n\n{completion.choices[0].message.content}"
        except Exception as e:
            err = str(e)
            if not is_transient(err):
                return f"🔴 **OpenRouter error (non-transient)**\n\n{err}"
            failures["OpenRouter"] = err[:120]
    else:
        failures["OpenRouter"] = "No OPENROUTER_API_KEY"

    github_token = st.secrets.get("GITHUB_MODELS_TOKEN")
    if github_token:
        try:
            from openai import OpenAI as OpenAIClient
            github_client = OpenAIClient(api_key=github_token, base_url="https://models.inference.ai.azure.com")
            completion = github_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": "You are a concise IBD-style market analyst."},
                          {"role": "user", "content": prompt}],
                max_tokens=400, temperature=0.4,
            )
            summary = format_unavailable_reasons(failures)
            return f"⬜ **GitHub Models / gpt-4o-mini** *({summary})*\n\n{completion.choices[0].message.content}"
        except Exception as e:
            err = str(e)
            if not is_transient(err):
                return f"🔴 **GitHub Models error (non-transient)**\n\n{err}"
            failures["GitHub Models"] = err[:120]
    else:
        failures["GitHub Models"] = "No GITHUB_MODELS_TOKEN"

    failure_lines = "\n".join(f"- {p}: {r}" for p, r in failures.items())
    return f"🔴 **All AI providers failed**\n\n{failure_lines}"

SECTOR_KEYWORDS = {
    "Healthcare": "#FF69B4", "Health Care": "#FF69B4", "Medical": "#FF69B4", "Medicals": "#FF69B4",
    "Biotech": "#FF69B4", "Pharma": "#FF69B4",
    "Energy": "#FF69B4", "Oil": "#FF69B4", "Gas": "#FF69B4", "Solar": "#FF69B4",
    "Financials": "#FF69B4", "Financial": "#FF69B4", "Banks": "#FF69B4", "Banking": "#FF69B4",
    "Industrials": "#FF69B4", "industrial ": "#FF69B4",
    "Materials": "#FF69B4", "Mining": "#FF69B4", "Chemicals": "#FF69B4",
    "Utilities": "#FF69B4", "Electric": "#FF69B4", "Elec": "#FF69B4", "tech": "#FF69B4",
    "Technology": "#FF69B4", "Software": "#FF69B4",
    "Semiconductor": "#FF69B4", "Semiconductors": "#FF69B4", "Semicon": "#FF69B4",
    "AI": "#FF69B4", "Artificial Intelligence": "#FF69B4",
    "Cybersecurity": "#FF69B4", "Security": "#FF69B4",
    "Consumer Discretionary": "#FF69B4", "Retail": "#FF69B4",
    "Consumer Staples": "#FF69B4",
    "Real Estate": "#FF69B4",
    "Communication Services": "#FF69B4",
    "Defense": "#FF69B4", "Aerospace": "#FF69B4", "biomed": "#FF69B4",
    "Insurance": "#FF69B4",
    "Transportation": "#FF69B4", "Shipping": "#FF69B4", "Airlines": "#FF69B4", "transport": "#FF69B4",
    "Housing": "#FF69B4", "Homebuilders": "#FF69B4",
    "Crypto": "#FF69B4", "Gold": "#FF69B4", "Broker": "#FF69B4", "Brokerage": "#FF69B4", "Rail": "#FF69B4", "railroads": "#FF69B4", 
    "Rails": "#FF69B4", "finance": "#FF69B4", "metals": "#FF69B4", "Payment Processing": "#FF69B4", 
    "travel": "#FF69B4", "airline": "#FF69B4", "fintech": "#FF69B4", "uranium": "#FF69B4", "mega-cap": "#FF69B4",
    "apparel": "#FF69B4", "risk-on": "#FF69B4", "risk-off": "#FF69B4", "New Highs": "#FF69B4", "New Lows": "#FF69B4", "biotechnology": "#FF69B4", 
}

def format_ai_analysis_text(text, tickers=None, industries=None):
    """
    Post-process AI markdown output to highlight key terms:
    - strips markdown syntax (**bold**, *italic*, ### headers) — plain text, no HTML tags
    - numbers/percentages (light color)
    - quadrant keywords: Strong/Improving/Weakening/Weak (color-coded)
    - BLUE DOT (red, bold)
    - ticker symbols (gold, bold)
    - industry names (teal, bold)
    Must be rendered with st.markdown(..., unsafe_allow_html=True).
    """
    if not text:
        return text

    # 0. Strip markdown syntax entirely — no asterisks, no HTML tags introduced.
    #    (Bold/color emphasis is added separately below via <span> for known terms.)
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)              # **bold** -> bold
    text = re.sub(r'(?<!\*)\*([^\*\n]+?)\*(?!\*)', r'\1', text)  # *italic* -> italic
    text = re.sub(r'^\s*#{1,6}\s*', '', text, flags=re.MULTILINE)  # ### Header -> Header

    # 1. Numbers/percentages FIRST — before any HTML is injected,
    #    so we don't accidentally bold digits inside hex color codes.
    text = re.sub(
        r'\b(\d+(?:\.\d+)?%?)\b',
        r'<span style="color:#FFE5CC; font-weight:bold;">\1</span>',
        text
    )

    # 2. Quadrant keywords — distinct color per label
    quadrant_colors = {
        "Strong":    "#00FF00",
        "Improving": "#378ADD",
        "Weakening": "#FFA500",
        "Weak":      "#FF4B4B",
    }
    for word, color in quadrant_colors.items():
        pattern = re.compile(rf'\b{word}\b', re.IGNORECASE)
        text = pattern.sub(
            lambda m, c=color: f'<span style="color:{c}; font-weight:bold;">{m.group(0)}</span>',
            text
        )

    industry_placeholders = {}
    if industries:
        for i, ind in enumerate(sorted(set(industries), key=len, reverse=True)):
            if not ind:
                continue
            token = f"@@IND{i}@@"
            pattern = re.compile(re.escape(ind), re.IGNORECASE)

            def _stash(m, token=token):
                industry_placeholders[token] = m.group(0)
                return token

            text = pattern.sub(_stash, text)

    for word, color in sorted(SECTOR_KEYWORDS.items(), key=lambda x: len(x[0]), reverse=True):
        pattern = re.compile(rf'\b{re.escape(word)}\b', re.IGNORECASE)
        text = pattern.sub(
            lambda m, c=color: f'<span style="color:{c}; font-weight:bold;">{m.group(0)}</span>',
            text
        )

    # 3. BLUE DOT
    text = re.sub(
        r'\bBLUE DOT\b',
        '<span style="color:#FF4B4B; font-weight:bold;">BLUE DOT</span>',
        text
    )

    # 4. Ticker symbols — case-sensitive, only known tickers to avoid false hits
    if tickers:
        for t in sorted(set(tickers), key=len, reverse=True):
            if not t or len(t) < 1:
                continue
            pattern = re.compile(rf'\b{re.escape(t)}\b')
            text = pattern.sub(
                f'<span style="color:#FFD700; font-weight:bold;">{t}</span>',
                text
            )

    # 5. Industry names — longest first, case-insensitive
    for token, original_text in industry_placeholders.items():
        text = text.replace(
            token,
            f'<span style="color:#4ecdc4; font-weight:bold;">{original_text}</span>'
        )

    return text

def parse_ai_points(raw_text):
    """Split an AI response into (provider_header, [(label, content), ...])."""
    if not raw_text:
        return None, []

    text = raw_text.strip()
    lines = text.split("\n")

    header = None
    if lines and re.match(r'^[🟦🟧⬜🟣🔴]', lines[0].strip()):
        header = lines[0].strip()
        rest_lines = lines[1:]
        while rest_lines and not rest_lines[0].strip():
            rest_lines.pop(0)
        body = "\n".join(rest_lines)
    else:
        body = text

    bullet_pattern  = re.compile(r'^\s*(?:[-•*]|\d+[\.\)])\s+')
    # Markdown headings: "### 2. Title", "## Title", "# Title", with or
    # without a leading number — each one becomes its own labeled row.
    heading_pattern = re.compile(r'^\s*#{1,6}\s*(?:\d+[\.\)]\s*)?(.+?)\s*#*\s*$')

    bullets = []
    current = ""
    for line in body.split("\n"):
        heading_match = heading_pattern.match(line)
        if heading_match:
            if current:
                bullets.append(current.strip())
            # Wrap as "**Title**" so the label-extraction step below picks
            # it up as its own row; any text that follows on subsequent
            # non-bullet lines gets appended as that row's content.
            current = f"**{heading_match.group(1).strip()}** "
        elif bullet_pattern.match(line):
            if current:
                bullets.append(current.strip())
            current = bullet_pattern.sub("", line, count=1)
        else:
            if current:
                current += " " + line.strip()
            elif line.strip():
                bullets.append(line.strip())
    if current:
        bullets.append(current.strip())

    points = []
    for i, b in enumerate(bullets, start=1):
        b = b.strip()
        label = None
        content = b

        m = re.match(r'^\*\*(.+?)\*\*[:\-]?\s*(.*)$', b)
        if m and m.group(2).strip():
            label = m.group(1).strip()
            content = m.group(2).strip()
        elif m:
            # Heading matched but had no content glued onto the same line —
            # the content will simply arrive as the next row instead.
            label = m.group(1).strip()
            content = ""
        else:
            m2 = re.match(r"^([A-Za-z][A-Za-z0-9 /&'\-]{2,45}):\s+(.+)$", b)
            if m2:
                label = m2.group(1).strip()
                content = m2.group(2).strip()

        if not label:
            label = f"Point {i}"

        points.append((label, content))

    return header, points

def render_ai_points_table(raw_text, tickers=None, industries=None):
    """Render an AI analysis response as a 2-column (topic | detail) table.
    Rows with no content (section headings like 'Outliers') span the full width."""
    if not raw_text:
        return

    header, points = parse_ai_points(raw_text)
    if not points:
        formatted = format_ai_analysis_text(raw_text, tickers=tickers, industries=industries)
        st.markdown(formatted, unsafe_allow_html=True)
        return

    rows_html = ""
    for i, (label, content) in enumerate(points):
        bg = "#1a1c23" if i % 2 == 0 else "#12141a"
        # Strip any stray markdown left in the label (e.g. "**Sub-Themes:**"
        # or a leftover "### " header prefix defaulting to "Point N").
        label_clean = re.sub(r'\*\*(.+?)\*\*', r'\1', label)
        label_clean = re.sub(r'^\s*#{1,6}\s*', '', label_clean).strip()

        if not content.strip():
            # Section-heading-only row (e.g. "Outliers") — merge into one
            # full-width cell instead of leaving column 2 blank.
            rows_html += (
                f"<tr style='background:{bg};'>"
                f"<td colspan='2' style='padding:8px 12px; border:2px solid #4a4f5a; "
                f"font-weight:700; color:#e0e0e0; font-size:14.5px;'>{label_clean}</td>"
                f"</tr>"
            )
            continue

        formatted_content = format_ai_analysis_text(content, tickers=tickers, industries=industries)
        rows_html += (
            f"<tr style='background:{bg};'>"
            f"<td style='padding:8px 12px; border:2px solid #4a4f5a ; vertical-align:top; "
            f"width:170px; font-weight:700; color:#e0e0e0; font-size:14.5px;'>{label_clean}</td>"
            f"<td style='padding:8px 12px; border:2px solid #4a4f5a ; vertical-align:top; "
            f"color:#e0e0e0; font-size:14.5px; line-height:1.5;'>{formatted_content}</td>"
            f"</tr>"
        )

    header_html = ""
    if header:
        header_clean = re.sub(r'\*\*(.+?)\*\*', r'\1', header)
        header_html = f"<div style='font-size:13px; color:#888; margin-bottom:6px;'>{header_clean}</div>"

    table_html = (
        f"{header_html}"
        f"<table style='width:100%; border-collapse:collapse; margin-bottom:6px; "
        f"border:3px solid #cccccc;'>"
        f"<tbody>{rows_html}</tbody></table>"
    )
    st.markdown(table_html, unsafe_allow_html=True)

# 6. Compact Display Logic
if all_data:
    df_main = pd.DataFrame([{"Industry": item["Industry"], "Group RS": item["Group RS"], "Group RS Prev": item["Group RS Prev"], "Group RS 1M": item["Group RS 1M"], "Group RS 3D": item["Group RS 3D"]} for item in all_data])

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

    # ── ROC (RS Thrust Rate %) ─────────────────────────────────────────────
    # Calibrated blend: 60% weight on current ("1-week") RS + 40% on 1-Month RS,
    # plus a small 0.1 acceleration adjustment vs the RS reading 3 trading days ago.
    df_main['ROC'] = (
        0.6 * df_main['Group RS']
        + 0.4 * df_main['Group RS 1M']
        + 0.1 * (df_main['Group RS'] - df_main['Group RS 3D'])
    )

    st.markdown("""
    <style>
    .ticker-badge { 
        display: inline-block; 
        margin: 1px 3px; 
        padding: 2px 6px; 
        border: 1px solid #444; 
        border-radius: 4px; 
        font-size: 12px; 
        line-height: 1.2; 
        background-color: #1e1e1e; 
        color: #eee; 
        white-space: nowrap;
    }
    .cloud-badge {
        background-color: #2e4a3e;
        border: 1px solid #4ecdc4;
    }
    .volatility-badge {
        padding: 2px 6px;
        border-radius: 4px;
        line-height: 1.2;
    }
    .volatility-badge .ticker-name,
    .volatility-badge .ticker-rs {
        font-size: 12px;
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
    .ticker-name { font-weight: bold; color: #ffffff; margin-right: 4px; font-size: 12px; }
    .ticker-rs { color: #4ecdc4; font-weight: normal; font-size: 12px; }
    table { width:100%; border-collapse: collapse; }
    th { padding: 4px 8px !important; background-color: #1f77b4; color: white; font-size: 13px; }
    td { padding: 2px 8px !important; border-bottom: 1px solid #333; font-size: 13px; }
    th:nth-child(3), td:nth-child(3),
    th:nth-child(6), td:nth-child(6) {
        border-right: 3px solid #ffffff;
    }
    th:nth-child(7), td:nth-child(7) {
        border-right: 3px solid #ff0000;
    }
    tbody tr:nth-child(21) td {
        border-top: 3px solid #ff0000;
    }
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

    table_html = """<table>
    <thead><tr>
    <th style="text-align: center; width: 30px;">#</th>
    <th style="text-align: center;">Industry</th>
    <th style="text-align: center; width: 40px;">RS</th>
    <th style="text-align: center; width: 40px;">1W</th>
    <th style="text-align: center; width: 40px;">1M</th>
    <th style="text-align: center; width: 40px;">△T</th>
    <th style="text-align: center; width: 400px;">Tickers (RS > 80)</th>
    <th style="text-align: center; width: 250px;">21ema_Valid</th>
    <th style="text-align: center; width: 170px;">21ema_Cloud</th>
    <th style="text-align: center; width: 170px;">21ema_Wick</th>
    <th style="text-align: center; width: 170px;">50ma_Bounce</th>
    </tr></thead><tbody>"""

    # Quick bullish-engulfing-today set (for industry-name lime highlight)
    _engulf_today_set = set()
    for _t in KNOWN_STOCKS:
        _df = ticker_dfs_shared.get(_t)
        if _df is None or len(_df) < 2:
            continue
        if (_df['Open'].iloc[-1] < _df['Low'].iloc[-2]) and (_df['Close'].iloc[-1] > _df['High'].iloc[-2]):
            _engulf_today_set.add(_t)

    # Quick botak-today set (single bar, for industry-name lime highlight)
    _botak_today_set = set()
    for _t in KNOWN_STOCKS:
        _df = ticker_dfs_shared.get(_t)
        if _df is None or len(_df) < 1:
            continue
        _o, _h, _c = _df['Open'].iloc[-1], _df['High'].iloc[-1], _df['Close'].iloc[-1]
        _is_botak = abs(_c - _h) < 0.05 and _c > _o
        _is_pct   = _c > _o and ((_c - _o) / max(_h - _o, 0.001)) > 0.9
        if (_is_botak or _is_pct) and _c > 20:
            _botak_today_set.add(_t)

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

        # ROC cell
        roc_val = row['ROC']
        if roc_val > 90:
            roc_str = f'<span style="border: 2px solid #32CD32; color: inherit; font-weight: bold; padding: 1px 6px; border-radius: 3px; display: inline-block;">{roc_val:.1f}</span>'
        else:
            roc_str = f'{roc_val:.1f}'
        
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
        engulf_industry_count = sum(1 for t in item["Tickers"]["Ticker"] if t in _engulf_today_set)
        botak_industry_count = sum(1 for t in item["Tickers"]["Ticker"] if t in _botak_today_set)
        for _, r in item["Tickers"].iterrows():
            ticker_sym = r["Ticker"]
            rs_score = r["RS Score"]
            ticker_price = item["Prices"].get(ticker_sym, 0)
            if new_style_industry_table and ticker_sym not in KNOWN_STOCKS:  # NEW: new style hides non-KNOWN_STOCKS tickers
                continue
            if ticker_sym in industry_vol_tickers.get(row["Industry"], []):
                ticker_glow = "box-shadow:0 0 6px 2px #FF4B4B;"
            elif engulf_industry_count > 1 and ticker_sym in _engulf_today_set:
                ticker_glow = "box-shadow:0 0 6px 2px #FFFF00;"
            elif botak_industry_count > 2 and ticker_sym in _botak_today_set:
                ticker_glow = "box-shadow:0 0 6px 2px #00FF00;"
            else:
                ticker_glow = ""
            rs_threshold = 70 if ticker_sym in LIME_STOCKS1 else 80
            
            if (show_all_rs or rs_score >= rs_threshold) and ticker_price > 20:
                # If the ticker is inside KNOWN_STOCKS, apply high-contrast dark text rules
                if ticker_sym in LIME_STOCKS1:
                    ticker_html += (
                        f'<div class="ticker-badge lime-badge" style="{ticker_glow}">'
                        f'<span class="ticker-name" style="color: #000000; font-weight: bold;">{ticker_sym}</span>' 
                        f'<span class="ticker-rs" style="color: #000000; font-weight: bold; margin-left: 5px;">{rs_score:.0f}</span>' 
                        f'</div>'
                    )
                elif ticker_sym in KNOWN_STOCKS:
                    ticker_html += (
                        f'<div class="ticker-badge new-pattern-badge" style="{ticker_glow}">'
                        f'<span class="ticker-name" style="color: #111111; font-weight: bold;">{ticker_sym}</span>' # Clean high-contrast dark charcoal text
                        f'<span class="ticker-rs" style="color: #004d26; font-weight: bold;">{r["RS Score"]:.0f}</span>' # Highly legible dark gold numbers
                        f'</div>'
                    )
                else:
                    # Standard matching dark badge layout for everything else
                    ticker_html += (
                        f'<div class="ticker-badge" style="{ticker_glow}">'
                        f'<span class="ticker-name">{ticker_sym}</span>'
                        f'<span class="ticker-rs">{r["RS Score"]:.0f}</span>'
                        f'</div>'
                    )
        
        #cloud_html = "".join([f'<div class="ticker-badge cloud-badge">{c}</div>' for c in item["Cloud"]])
        cloud_html = ""
        sorted_cloud = sorted(item["Cloud"], key=lambda sym: rs_lookup.get(sym, 0), reverse=True)
        if new_style_industry_table:  # NEW: new style hides non-KNOWN_STOCKS tickers
            sorted_cloud = [s for s in sorted_cloud if s in KNOWN_STOCKS]

        # --- SLICE LOGIC: Slices the sorted array to isolate the top 5 items only ---
        top_5_cloud = sorted_cloud if show_all_setups else sorted_cloud[:5]
        
        for cloud_sym in top_5_cloud:
            # Retrieve the RS Score from our data map (default to 0 if not found)
            cloud_rs = rs_lookup.get(cloud_sym, 0)
            
            if cloud_sym in LIME_STOCKS1:
                cloud_html += (
                    f'<div class="ticker-badge lime-badge">'
                    f'<span class="ticker-name" style="color: #000000; font-weight: bold;">{cloud_sym}</span>'
                    f'<span class="ticker-rs" style="color: #000000; font-weight: bold; margin-left: 5px;">{cloud_rs:.0f}</span>'
                    f'</div>'
                )
            elif cloud_sym in KNOWN_STOCKS:
                cloud_html += (
                    f'<div class="ticker-badge" style="background-color:#FF69B4; border:1px solid #C71585;">'
                    f'<span class="ticker-name" style="color: #111111; font-weight: bold;">{cloud_sym}</span>'
                    f'<span class="ticker-rs" style="color: #4B0026; font-weight: bold;">{cloud_rs:.0f}</span>'
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
        if new_style_industry_table:  # NEW: new style hides non-KNOWN_STOCKS tickers
            sorted_cloud_21ema = [s for s in sorted_cloud_21ema if s in KNOWN_STOCKS]
        top_5_cloud_21ema = sorted_cloud_21ema if show_all_setups else sorted_cloud_21ema[:5]

        for cloud_sym in top_5_cloud_21ema:
            cloud_rs = rs_lookup.get(cloud_sym, 0)

            if cloud_sym in LIME_STOCKS1:
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
        if new_style_industry_table:  # NEW: new style hides non-KNOWN_STOCKS tickers
            sorted_cloud_wick = [s for s in sorted_cloud_wick if s in KNOWN_STOCKS]
        top_5_cloud_wick = sorted_cloud_wick if show_all_setups else sorted_cloud_wick[:5]

        for cloud_sym in top_5_cloud_wick:
            cloud_rs = rs_lookup.get(cloud_sym, 0)

            if cloud_sym in LIME_STOCKS1:
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
        if new_style_industry_table:  # NEW: new style hides non-KNOWN_STOCKS tickers
            sorted_ma50_bounce = [s for s in sorted_ma50_bounce if s in KNOWN_STOCKS]
        top_5_ma50_bounce = sorted_ma50_bounce if show_all_setups else sorted_ma50_bounce[:5]

        for cloud_sym in top_5_ma50_bounce:
            cloud_rs = rs_lookup.get(cloud_sym, 0)

            if cloud_sym in LIME_STOCKS1:
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

        num_color = "#FF4B4B" if row["Industry"] in vol_flagged_industries else "#888888"

        industry_name_color = (
            "#FF4B4B" if row["Industry"] in vol_flagged_industries
            else "#FFFF00" if engulf_industry_count > 1
            else "#00FF00" if botak_industry_count > 2
            else "#ffffff"
        )
        
        table_html += f"""<tr style="background-color: {bg_color};">
        <td style="text-align: center; color: {num_color}; font-weight: bold;">{row_num}</td>
        <td style="font-weight: bold; color: {industry_name_color};">{row['Industry']}</td>
        <td style="text-align: center; color: #4ecdc4; font-weight: bold;">{row['Group RS']:.1f}</td>
        <td style="text-align: center; vertical-align: middle;">{rank_str}</td>
        <td style="text-align: center; vertical-align: middle;">{rank_str_1m}</td>
        <td style="text-align: center; vertical-align: middle;">{roc_str}</td>
        <td>{ticker_html}</td>
        <td>{cloud_html}</td>
        <td>{cloud_21ema_html}</td>
        <td>{cloud_wick_html}</td>
        <td>{ma50_bounce_html}</td></tr>"""

    table_html += "</tbody></table>"

    # ── Top 20 industries theme insight ──────────────────────────────────
    top20_sig = (
        str(df_main.head(20)["Industry"].tolist())
        + str(round(df_main.head(20)["Group RS"].sum(), 1))
        + str(sorted(new_high_tickers)) + str(sorted(new_low_tickers))
    )
    force_theme = st.button("🔄 Refresh Theme Insight", key="retry_top20_theme")

    if force_theme or st.session_state.get("top20_theme_key") != top20_sig:
        with st.spinner("Analyzing top 20 industry theme..."):
            theme_result = timed(
                "generate_top_industries_theme_insight",
                generate_top_industries_theme_insight,
                df_main, all_data, 20,
                new_high_tickers, new_low_tickers
            )
        if theme_result:
            st.session_state["top20_theme_result"] = theme_result
            st.session_state["top20_theme_key"] = top20_sig

    if "top20_theme_result" in st.session_state:
        top20_industries = df_main.head(20)["Industry"].tolist()
        top20_tickers = []
        for industry in top20_industries:
            item = next((d for d in all_data if d["Industry"] == industry), None)
            if item is not None:
                known_only = item["Tickers"][item["Tickers"]["Ticker"].isin(KNOWN_STOCKS)]
                top5 = known_only.sort_values("RS Score", ascending=False).head(5)
                top20_tickers.extend(top5["Ticker"].tolist())

        combined_tickers = list(set(top20_tickers) | set(new_high_tickers) | set(new_low_tickers))

        # ── NEW: also pull in industries that New High / New Low tickers belong to ──
        def _local_industry_set(ticker_list, industries_dict):
            found = set()
            for t in ticker_list:
                for industry, tickers in industries_dict.items():
                    if t in tickers:
                        found.add(industry)
            return found

        nh_nl_industries = _local_industry_set(new_high_tickers, INDUSTRIES) | _local_industry_set(new_low_tickers, INDUSTRIES)
        combined_industries = list(set(top20_industries) | nh_nl_industries)

        render_ai_points_table(
            st.session_state["top20_theme_result"],
            tickers=combined_tickers,
            industries=combined_industries
        )

    all_vol_tickers = set()
    for tickers_list in industry_vol_tickers.values():
        all_vol_tickers.update(tickers_list)
    total_vol_ticker_count = len(all_vol_tickers)

    dist_html = (
        f"<div style='font-size:14px; font-weight:bold; color:#ffffff; margin:14px 0 6px;'>"
        f"📉 Distribution Cluster "
        f"<span style='color:#FF4B4B;'>({len(vol_flagged_industries)} industries, {total_vol_ticker_count} tickers)</span>"
        f"</div>"
    )
    if vol_flagged_industries:
        # Order by current table rank so it reads top-to-bottom like the main table
        sorted_flagged = sorted(
            vol_flagged_industries,
            key=lambda ind: industry_rank_map.get(ind, 9999)
        )
        for industry in sorted_flagged:
            rank = industry_rank_map.get(industry, "-")
            tickers_for_ind = sorted(industry_vol_tickers.get(industry, []))
            ticker_badges = "".join(
                f'<span style="display:inline-block;margin:1px 3px;padding:1px 5px;'
                f'border:1px solid #663333;border-radius:3px;font-size:11px;'
                f'background-color:#2d1a1a;color:#FF9999;font-weight:600;">{t}</span>'
                for t in tickers_for_ind
            )
            dist_html += (
                f"<div style='margin-bottom:5px;'>"
                f"<span style='color:#FF4B4B; font-weight:bold; font-size:12px; display:inline-block; min-width:34px;'>#{rank}</span>"
                f"<span style='color:#FF4B4B; font-weight:bold; font-size:13px; display:inline-block; min-width:200px;'>{industry}</span>"
                f"<span>{ticker_badges}</span>"
                f"</div>"
            )
    st.markdown(dist_html, unsafe_allow_html=True)

    # ── Engulfing summary (industries with >1 bullish-engulfing-today ticker) ──
    engulf_industry_tickers = {}
    for _, row_e in df_main.iterrows():
        item_e = next((d for d in all_data if d["Industry"] == row_e["Industry"]), None)
        if item_e is None:
            continue
        tickers_e = sorted(t for t in item_e["Tickers"]["Ticker"] if t in _engulf_today_set)
        if len(tickers_e) > 1:
            engulf_industry_tickers[row_e["Industry"]] = tickers_e

    all_engulf_tickers = set()
    for tickers_list in engulf_industry_tickers.values():
        all_engulf_tickers.update(tickers_list)

    engulf_html = (
        f"<div style='font-size:14px; font-weight:bold; color:#ffffff; margin:14px 0 6px;'>"
        f"🐳🐳 Engulfing Cluster "
        f"<span style='color:#FFFF00;'>({len(engulf_industry_tickers)} industries, {len(all_engulf_tickers)} tickers)</span>"
        f"</div>"
    )
    if engulf_industry_tickers:
        sorted_engulf = sorted(
            engulf_industry_tickers.keys(),
            key=lambda ind: industry_rank_map.get(ind, 9999)
        )
        for industry in sorted_engulf:
            rank = industry_rank_map.get(industry, "-")
            tickers_for_ind = engulf_industry_tickers[industry]
            ticker_badges = "".join(
                f'<span style="display:inline-block;margin:1px 3px;padding:1px 5px;'
                f'border:1px solid #8a6d00;border-radius:3px;font-size:11px;'
                f'background-color:#3a2f00;color:#ffe066;font-weight:600;">{t}</span>'
                for t in tickers_for_ind
            )
            engulf_html += (
                f"<div style='margin-bottom:5px;'>"
                f"<span style='color:#FFFF00; font-weight:bold; font-size:12px; display:inline-block; min-width:34px;'>#{rank}</span>"
                f"<span style='color:#FFFF00; font-weight:bold; font-size:13px; display:inline-block; min-width:200px;'>{industry}</span>"
                f"<span>{ticker_badges}</span>"
                f"</div>"
            )
    st.markdown(engulf_html, unsafe_allow_html=True)

    # ── Botak summary (industries with >1 botak-today ticker) ──
    botak_industry_tickers = {}
    for _, row_bk in df_main.iterrows():
        item_bk = next((d for d in all_data if d["Industry"] == row_bk["Industry"]), None)
        if item_bk is None:
            continue
        tickers_bk = sorted(t for t in item_bk["Tickers"]["Ticker"] if t in _botak_today_set)
        if len(tickers_bk) > 2:
            botak_industry_tickers[row_bk["Industry"]] = tickers_bk

    all_botak_tickers = set()
    for tickers_list in botak_industry_tickers.values():
        all_botak_tickers.update(tickers_list)

    botak_html = (
        f"<div style='font-size:14px; font-weight:bold; color:#ffffff; margin:14px 0 6px;'>"
        f"🧑‍🦲🧑‍🦲🧑‍🦲 Botak Cluster "
        f"<span style='color:#00FF00;'>({len(botak_industry_tickers)} industries, {len(all_botak_tickers)} tickers)</span>"
        f"</div>"
    )
    if botak_industry_tickers:
        sorted_botak = sorted(botak_industry_tickers.keys(), key=lambda ind: industry_rank_map.get(ind, 9999))
        for industry in sorted_botak:
            rank = industry_rank_map.get(industry, "-")
            tickers_for_ind = botak_industry_tickers[industry]
            ticker_badges = "".join(
                f'<span style="display:inline-block;margin:1px 3px;padding:1px 5px;'
                f'border:1px solid #336633;border-radius:3px;font-size:11px;'
                f'background-color:#1a2d1a;color:#99FF99;font-weight:600;">{t}</span>'
                for t in tickers_for_ind
            )
            botak_html += (
                f"<div style='margin-bottom:5px;'>"
                f"<span style='color:#00FF00; font-weight:bold; font-size:12px; display:inline-block; min-width:34px;'>#{rank}</span>"
                f"<span style='color:#00FF00; font-weight:bold; font-size:13px; display:inline-block; min-width:200px;'>{industry}</span>"
                f"<span>{ticker_badges}</span>"
                f"</div>"
            )
    st.markdown(botak_html, unsafe_allow_html=True)

    st.markdown(
        f'<div style="text-align: right; font-size: 20px; color: #888888; margin-bottom: 4px; font-family: monospace;">'
        f'Setup = <span style="color: #4ecdc4; font-weight: bold;">{global_setup_count}</span>'
        f'<span style="color: #888888; font-size: 16px; margin-left: 6px;">{setup_rank_str}</span></div>',
        unsafe_allow_html=True
    )

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
            if len(df) < 260:   # bumped from 250 → 260 to match pine7's lookback needs
                continue
            try:
                close = df['Close']
                high  = df['High']
                low   = df['Low']

                rs = close / benchmark_df_leader['Close']
                rsMA = rs.ewm(span=21, adjust=False).mean()
                histNH = rs.rolling(250).max()
                sma50 = close.rolling(50).mean()
                sma150 = close.rolling(150).mean()
                sma200 = close.rolling(200).mean()

                circleCond = (rs == histNH)
                circleCount30 = circleCond.rolling(30).sum()
                twoCircles30 = circleCount30 >= 2

                # Pine7 as a boolean Series (mirrors process_pattern_scanners)
                c_sma200_22 = sma200.shift(22)
                c_highest   = high.rolling(260).max()
                c_lowest    = low.rolling(260).min()
                pine7_s = (
                    ((close > sma150) & (close > sma200)).astype(int)
                    + (sma150 > sma200).astype(int)
                    + (sma200 > c_sma200_22).astype(int)
                    + (sma150 > sma200).astype(int)
                    + (close > sma50).astype(int)
                    + (((close / c_lowest) - 1) * 100 >= 25).astype(int)
                    + ((1 - (close / c_highest)) * 100 <= 25).astype(int)
                ) == 7

                leader_series = (
                    (twoCircles30 | circleCond) &
                    (close > sma50) &
                    (close > sma200) &
                    (close >= 20) &
                    (pine7_s | (rs > rsMA))
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

@st.cache_data(ttl=3600)
def compute_stage_history(stocks_list, ticker_dfs, benchmark_df_input):
    """
    Vectorized version of the Stage logic in compute_breadth_and_stage,
    evaluated across the full time series (not just the latest bar) so we
    can get daily Stage 2 / Stage 4 counts for the trailing 60 days.
    """
    try:
        if benchmark_df_input is None or benchmark_df_input.empty:
            return pd.DataFrame()

        bm_idx = benchmark_df_input.index.tz_localize(None) if benchmark_df_input.index.tz is not None else benchmark_df_input.index
        bm_aligned = benchmark_df_input.copy()
        bm_aligned.index = bm_idx

        stage2_list = []
        stage4_list = []

        for ticker in stocks_list:
            try:
                df = ticker_dfs.get(ticker)
                if df is None or len(df) < 260:
                    continue

                df_idx = df.index.tz_localize(None) if df.index.tz is not None else df.index
                df_aligned = df.copy()
                df_aligned.index = df_idx

                combined = pd.merge(
                    df_aligned[['Close', 'Open']],
                    bm_aligned[['Close']].rename(columns={'Close': 'Close_bench'}),
                    left_index=True, right_index=True, how='inner'
                )
                if len(combined) < 260:
                    continue

                ema126 = df_aligned['Close'].ewm(span=126, adjust=False).mean().reindex(combined.index, method='ffill')
                rs = combined['Close'] / combined['Close_bench']

                ema_spans = [21, 42, 63, 72, 84, 126, 147, 168]
                r = {s: rs.ewm(span=s, adjust=False).mean() for s in ema_spans}

                c, o, rsme = combined['Close'], combined['Open'], rs

                stage1_cond = (rsme >= r[84]) & (rsme < r[126])
                stage3_cond = (
                    (rsme < r[42]) & (rsme >= r[72]) & (rsme >= r[84]) & (rsme >= r[126])
                    & ((r[42] > r[63]) | (rsme < r[63])) & (r[63] > r[126]) & (c >= ema126)
                )
                stage2a_cond = (
                    (rsme >= r[168]) & (rsme >= r[147]) & (rsme >= r[126])
                    & (c >= ema126) & ((r[21] >= r[42]) | (r[42] >= r[63]))
                )
                stage2b_cond = (rsme >= r[126]) & (c >= ema126) & ((r[21] >= r[42]) | (r[42] >= r[63]))
                stage4_cond = ((rsme < r[63]) & (rsme < r[126])) | ((r[63] < r[126]) & (rsme < r[126]))

                stage2_final = (~stage1_cond & ~stage3_cond & (stage2a_cond | stage2b_cond))
                stage4_final = (~stage1_cond & ~stage3_cond & ~stage2a_cond & ~stage2b_cond & stage4_cond)

                stage2_list.append(stage2_final.astype(int))
                stage4_list.append(stage4_final.astype(int))
            except Exception:
                continue

        if not stage2_list:
            return pd.DataFrame()

        s2_daily = pd.concat(stage2_list, axis=1).fillna(0).sum(axis=1)
        s4_daily = pd.concat(stage4_list, axis=1).fillna(0).sum(axis=1)

        result = pd.DataFrame({
            "Date": s2_daily.index,
            "S2 Count": s2_daily.values,
            "S4 Count": s4_daily.values,
        }).tail(60)
        result["Date"] = pd.to_datetime(result["Date"]).dt.strftime("%Y-%m-%d")
        return result.reset_index(drop=True)
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def compute_gapper_history(stocks_list, _ticker_dfs):
    """
    Vectorized-per-ticker daily count of tickers meeting the Gapper Earning
    Drift condition (unfilled gap-up, still within 30 bars of the gap) —
    mirrors the scan logic inside process_pattern_scanners, evaluated
    across the FULL time series for a 60-day breadth history.
    """
    try:
        if not _ticker_dfs:
            return pd.DataFrame()

        all_series = []
        for ticker, df in _ticker_dfs.items():
            if not all(col in df.columns for col in ['Open', 'High', 'Low', 'Close']):
                continue
            if len(df) < 22:
                continue
            try:
                df_g = df.copy().reset_index(drop=True)
                strict_gap = df_g['Low'] > df_g['High'].shift(1)
                gap_pct = (df_g['Close'] / df_g['Close'].shift(1)) - 1
                max_gap_200 = gap_pct.shift(1).rolling(200, min_periods=1).max()

                gapUp10 = strict_gap & (
                    (gap_pct >= 0.10) |
                    (gap_pct >= max_gap_200 * 0.99)
                )

                bars_since_g        = pd.Series(np.inf, index=df_g.index)
                gap_floor_g         = pd.Series(np.nan, index=df_g.index)
                gap_ceiling_g       = pd.Series(np.nan, index=df_g.index)
                min_low_since_gap_g = pd.Series(np.nan, index=df_g.index)

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
                            if run_min_g <= fl_g:
                                ctr_g     = np.inf
                                fl_g      = np.nan
                                ceil_g    = np.nan
                                run_min_g = np.nan
                    bars_since_g.iloc[i]        = ctr_g
                    gap_floor_g.iloc[i]         = fl_g
                    gap_ceiling_g.iloc[i]       = ceil_g
                    min_low_since_gap_g.iloc[i] = run_min_g

                gapIn20_g      = bars_since_g        <= 30
                validGap_g     = gap_floor_g         <  gap_ceiling_g
                strictUnfill_g = min_low_since_gap_g >  gap_floor_g
                result_g = (gapIn20_g & strictUnfill_g & validGap_g & (df_g['Close'] >= 20)).astype(int)
                result_g.index = df.index  # restore original datetime index

                all_series.append(result_g)
            except Exception:
                continue

        if not all_series:
            return pd.DataFrame()

        combined = pd.concat(all_series, axis=1).fillna(0)
        daily_counts = combined.sum(axis=1)

        result = daily_counts.tail(60).reset_index()
        result.columns = ["Date", "Gapper Count"]
        result["Date"] = pd.to_datetime(result["Date"]).dt.strftime("%Y-%m-%d")
        return result
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=3600)
def compute_volatility_history(stocks_list, _ticker_dfs):
    """
    Vectorized daily count of tickers with a daily-range Z-score >= 2
    (vs its own 20-day mean/stdev) — mirrors compute_volatility_pickup,
    evaluated across the full time series for a 60-day breadth history.
    """
    try:
        if not _ticker_dfs:
            return pd.DataFrame()

        all_series = []
        for ticker, df in _ticker_dfs.items():
            if not all(col in df.columns for col in ['High', 'Low', 'Close']):
                continue
            if len(df) < 22:
                continue
            try:
                high, low, close = df['High'], df['Low'], df['Close']
                daily_range = 100 * (high / low - 1)
                avg_range   = daily_range.rolling(20).mean()
                std_range   = daily_range.rolling(20).std(ddof=1)
                z_series    = (daily_range - avg_range) / std_range.replace(0, np.nan)

                cond = (z_series >= 2) & (close >= 20)
                all_series.append(cond.astype(int))
            except Exception:
                continue

        if not all_series:
            return pd.DataFrame()

        combined = pd.concat(all_series, axis=1).fillna(0)
        daily_counts = combined.sum(axis=1)

        result = daily_counts.tail(60).reset_index()
        result.columns = ["Date", "Volatility Count"]
        result["Date"] = pd.to_datetime(result["Date"]).dt.strftime("%Y-%m-%d")
        return result
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=3600)
def compute_value_trap_history(stocks_list, _ticker_dfs):
    """
    Vectorized daily count of tickers meeting the Value Trap condition
    (price roughly -4x ATR below its 50-day MA) — mirrors the scan logic
    inside process_pattern_scanners, evaluated across the full time series
    for a 60-day breadth history.
    """
    try:
        if not _ticker_dfs:
            return pd.DataFrame()

        all_series = []
        for ticker, df in _ticker_dfs.items():
            if not all(col in df.columns for col in ['High', 'Low', 'Close']):
                continue
            if len(df) < 50:
                continue
            try:
                high, low, close = df['High'], df['Low'], df['Close']

                high_low   = high - low
                high_close = (high - close.shift(1)).abs()
                low_close  = (low  - close.shift(1)).abs()
                tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
                atr14   = tr.rolling(14).mean()
                atr_pct = (atr14 / close) * 100

                sma50    = close.rolling(50).mean()
                pct_gain = ((close - sma50) / sma50) * 100

                atr_mult2 = pct_gain / atr_pct.replace(0, 0.001)
                atr_mult2 = atr_mult2.replace([np.inf, -np.inf], np.nan)
                atr_mult  = (atr_mult2.fillna(0) * 10).astype(int) / 10

                cond = (atr_mult <= -4) & (close >= 20)
                all_series.append(cond.astype(int))
            except Exception:
                continue

        if not all_series:
            return pd.DataFrame()

        combined = pd.concat(all_series, axis=1).fillna(0)
        daily_counts = combined.sum(axis=1)

        result = daily_counts.tail(60).reset_index()
        result.columns = ["Date", "Value Trap Count"]
        result["Date"] = pd.to_datetime(result["Date"]).dt.strftime("%Y-%m-%d")
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
def compute_global_setup_count_history(stocks_list, _ticker_dfs):
    """
    Vectorized daily count of tickers meeting ANY of the three setup
    conditions (21ema_cloud, 21ema_wick, 50ma_bounce) — mirrors the scalar
    per-ticker logic inside get_rs_and_cloud_data_cached, but evaluated
    across the FULL time series so we get a real day-by-day Setup Count
    history (not just today's frozen ticker list re-ranked historically).
    """
    try:
        if not _ticker_dfs:
            return pd.DataFrame()

        all_setup_series = []

        for ticker in stocks_list:
            df = _ticker_dfs.get(ticker)
            if df is None or len(df) < 260:
                continue
            try:
                close = df['Close']; high = df['High']; low = df['Low']; open_ = df['Open']

                ema21_close  = close.ewm(span=21, adjust=False).mean()
                ema21_low_s  = low.ewm(span=21, adjust=False).mean()
                ema21_high_s = high.ewm(span=21, adjust=False).mean()
                sma50  = close.rolling(50).mean()
                sma150 = close.rolling(150).mean()
                sma200 = close.rolling(200).mean()

                ma50Rising = (sma50 > sma50.shift(1)) & (sma50.shift(1) > sma50.shift(2))

                powerma  = close.ewm(span=50, adjust=False).mean()
                gradient = powerma.diff()

                tr = pd.concat([
                    high - low,
                    (high - close.shift(1)).abs(),
                    (low - close.shift(1)).abs()
                ], axis=1).max(axis=1)
                atr = tr.rolling(14).mean()
                atrPercent = (atr / close) * 100

                atr21_R = (((close - ema21_close) / close) * 100) / (atrPercent + 1e-6)
                atr50_R = (((close - sma50) / close) * 100) / (atrPercent + 1e-6)
                emaDistPercent = ((close - ema21_low_s) / close) * 100

                hl_ratio   = high / low
                adrPercent = 100 * (hl_ratio.rolling(20).mean() - 1)

                cond1 = (adrPercent >= 2.45) & (adrPercent < 8.05)
                cond2 = (atr21_R >= -0.5) & (atr21_R <= 1)
                cond3 = (atr50_R >= 0) & (atr50_R <= 3)
                cond4 = (emaDistPercent > 0) & (emaDistPercent <= 8)
                pbb_cond2 = gradient >= 0

                c_sma200_22 = sma200.shift(22)
                c_highest   = high.rolling(260).max()
                c_lowest    = low.rolling(260).min()
                pine7_s = (
                    ((close > sma150) & (close > sma200)).astype(int)
                    + (sma150 > sma200).astype(int)
                    + (sma200 > c_sma200_22).astype(int)
                    + (sma150 > sma200).astype(int)
                    + (close > sma50).astype(int)
                    + (((close / c_lowest) - 1) * 100 >= 25).astype(int)
                    + ((1 - (close / c_highest)) * 100 <= 25).astype(int)
                ) == 7

                buyable = (
                    cond1 & cond2 & cond3 & cond4 & pbb_cond2 &
                    ma50Rising & (close >= 20) & pine7_s
                )

                # 21 EMA Cloud finalCondition (mirrors scalar block)
                insideCloud = (ema21_low_s <= close) & (close <= ema21_high_s)
                insideCloud3Days = insideCloud & insideCloud.shift(1) & insideCloud.shift(2)
                insideCloud2DaysPositive = (
                    insideCloud & insideCloud.shift(1) &
                    (close > close.shift(1)) & (close > open_)
                )
                bodyTop    = pd.concat([open_, close], axis=1).max(axis=1)
                bodyBottom = pd.concat([open_, close], axis=1).min(axis=1)
                bodySize   = bodyTop - bodyBottom
                insideBody = (
                    pd.concat([bodyTop, ema21_high_s], axis=1).min(axis=1)
                    - pd.concat([bodyBottom, ema21_low_s], axis=1).max(axis=1)
                ).clip(lower=0)
                insidePct = (insideBody / bodySize.replace(0, np.nan)).fillna(0)
                bodyCloud3Days = (insidePct >= 0.70) & (insidePct.shift(1) >= 0.70) & (insidePct.shift(2) >= 0.70)
                finalCondition = bodyCloud3Days | insideCloud3Days | insideCloud2DaysPositive

                cloud21ema_cond = buyable & finalCondition & (close >= 20)

                # 21 EMA Wick condition
                rangeToday = high - low
                lowerWick  = pd.concat([open_, close], axis=1).min(axis=1) - low
                longWick   = (lowerWick / rangeToday.replace(0, np.nan) > 0.5).fillna(False)
                cloud_wick_cond = buyable & longWick & (close >= 20)

                # 50MA Bounce condition
                fiftyday_percent  = (close - sma50) / sma50 * 100
                fiftyday_percent2 = (fiftyday_percent * 10).fillna(0).astype(int) / 10
                touchMA50_yest    = low.shift(1) <= sma50.shift(1)
                recover1          = touchMA50_yest & (close > sma50)
                ma50_bounce_cond = (
                    recover1 & cond1 & (fiftyday_percent2 <= 8) &
                    ma50Rising & (close >= 20) & pine7_s
                )

                setup_today = (cloud21ema_cond | cloud_wick_cond | ma50_bounce_cond).astype(int)
                all_setup_series.append(setup_today)
            except Exception:
                continue

        if not all_setup_series:
            return pd.DataFrame()

        combined = pd.concat(all_setup_series, axis=1).fillna(0)
        daily_counts = combined.sum(axis=1)

        result = daily_counts.tail(60).reset_index()
        result.columns = ["Date", "Setup Count"]
        result["Date"] = result["Date"].dt.strftime("%Y-%m-%d")
        return result
    except Exception:
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
        font=dict(size=16, color="#f2c500", family="Arial Black"),
        xanchor="center",
        bgcolor="rgba(0,0,0,0.12)",
        borderpad=3,
    )
    q_strong    = sum(1 for p in quad_points if p["weekly_rs"] >= 50 and p["monthly_rs"] >= 50)
    q_improving = sum(1 for p in quad_points if p["weekly_rs"] >= 50 and p["monthly_rs"] <  50)
    q_weakening = sum(1 for p in quad_points if p["weekly_rs"] <  50 and p["monthly_rs"] >= 50)
    q_weak      = sum(1 for p in quad_points if p["weekly_rs"] <  50 and p["monthly_rs"] <  50)

    quad_title_color = "#00FF00" if (q_strong + q_improving) > (q_weak + q_weakening) else "#FF6B6B"

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
            text="Industry RS — Weekly vs Monthly (Long Term)",
            x=0.5,
            xanchor="center",
            font=dict(size=16, color=quad_title_color),
        ),
        xaxis=dict(
            title="Weekly RS",
            range=[0, 100],
            dtick=10,
            showgrid=True,
            gridcolor="rgba(120,120,120,0.18)",
            zeroline=False,
            tickfont=dict(color="#aaaaaa", size=11),
            title_font=dict(color=quad_title_color, size=22),   # ← changed from "#aaaaaa"
        ),
        yaxis=dict(
            title="Monthly RS",
            range=[0, 100],
            dtick=10,
            showgrid=True,
            gridcolor="rgba(120,120,120,0.18)",
            zeroline=False,
            tickfont=dict(color="#aaaaaa", size=11),
            title_font=dict(color=quad_title_color, size=22),   # ← changed from "#aaaaaa"
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

        with st.spinner("Computing Stage history..."):
            stage_hist = timed(
                "compute_stage_history",
                compute_stage_history,
                stocks_tuple, ticker_dfs_shared, benchmark_df_shared
            )

        if not stage_hist.empty:
            fig_stage = go.Figure()
            fig_stage.add_trace(go.Scatter(
                x=stage_hist["Date"], y=stage_hist["S2 Count"],
                mode="lines", name="", line=dict(color="#378ADD", width=2), showlegend=False
            ))
            fig_stage.add_trace(go.Scatter(
                x=stage_hist["Date"], y=stage_hist["S4 Count"],
                mode="lines", name="", line=dict(color="#FF69B4", width=2), showlegend=False
            ))
            fig_stage.update_layout(
                height=260,
                margin=dict(l=20, r=20, t=10, b=20),
                plot_bgcolor="rgba(20,22,30,1)",
                paper_bgcolor="rgba(13,17,23,0)",
                font=dict(color="#cccccc"),
                legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="center", x=0.5),
                xaxis=dict(showgrid=False, tickfont=dict(size=9, color="#888888")),
                yaxis=dict(showgrid=True, gridcolor="rgba(120,120,120,0.15)", tickfont=dict(color="#888888")),
            )
            st.plotly_chart(fig_stage, use_container_width=True)

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
        <span style="color:#888; font-size:12px;">(Long term)</span>
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

pct_color = "#00FF00" if know_pos_pct >= 50 else "#FF4B4B"
st.markdown(
    f"#### ⭐ Minervini ("
    f"Positive Pct = <span style='color:{pct_color};'>{know_pos_pct:.1f}%</span> ... "
    #f"+ve Count: {know_positive_count} ... "
    f"Total = {know_total_count} ... "
    f"ATH = {len(ath_list)})",
    unsafe_allow_html=True,
)

if email_content_stocks or email_content_removed:
    minervini_html = ""

    minervini_syms = [sym for sym, _, _ in email_content_stocks]
    minervini_industry_counts, minervini_ticker_industry = build_leader_industry_map(minervini_syms, INDUSTRIES)

    for sym, is_new_addition, is_positive_today in sorted(email_content_stocks, key=lambda x: x[0]):

        if sym in ath_list:
            up_logo = "<span style='color:#00FF00; margin-right:4px; font-weight:bold;'>▲</span>"#FF4B4B
        #elif is_positive_today:
        #    up_logo = "<span style='color:#00FF00; margin-right:4px; font-weight:bold;'>▲</span>"
        else:
            up_logo = ""

        #has_setup_badge = sym in (ma50bounce_all | cloudwick_all | cloud21ema_all)
        glow_style = ""
        #if has_setup_badge:
        industries = minervini_ticker_industry.get(sym, [])
        ranks = [industry_rank_map[ind] for ind in industries if ind in industry_rank_map]
        is_top20_industry = any(r <= 20 for r in ranks) if ranks else False
        if is_top20_industry:
            glow_style = "box-shadow:0 0 8px 2px #FF4B4B; border:1px solid #FF4B4B;"

        minervini_html += setup_badge(
            sym,
            is_new=False,          #is_new_addition
            extra_prefix=up_logo,
            extra_style=glow_style,
        )

    for sym in sorted(email_content_removed):
        minervini_html += setup_badge(sym, is_removed=True)

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
    ma_line_color = status_color if 'status_color' in dir() else "#FF4B4B"
    st.line_chart(
        data=chart_df_minervini,
        x="Date",
        y=["Minervini Count", "20D MA"],
        color=["#1f77b4", ma_line_color],
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
st.markdown(f"#### 🔵 Blue Dot = Short term ({len([s for s in leader_rs_nh_matches if s != 'SPY'])})")

if leader_list or leader_yest:

    # ── NEW: map leaders to industries so we can check top-20 rank ──
    leader_industry_counts, leader_ticker_industry = build_leader_industry_map(leader_list, INDUSTRIES)

    html_leader = ""

    for sym in leader_list:
        dot = (
            '<span style="'
            'display:inline-block;width:7px;height:7px;'
            'border-radius:50%;background:#378ADD;'
            'box-shadow:0 0 5px 2px #378ADD;'
            'margin-right:4px;vertical-align:middle;'
            '"></span>'
            if sym in leader_rs_nh_matches and sym != "SPY" else ""
        )

        streak = leader_streaks.get(sym, 0)
        streak_color = "#FF4B4B" if streak >= 10 else "#333333" if sym in (ma50bounce_all | cloudwick_all | cloud21ema_all) else "#888888"
        streak_html = (
            f'<span style="color:{streak_color}; font-size:11px; margin-left:5px;"> {streak}</span>'
            if streak > 0 else ""
        )

        # ── NEW: glow if this leader's setup-industry is currently top 20 ──
        industries = leader_ticker_industry.get(sym, [])
        ranks = [industry_rank_map[ind] for ind in industries if ind in industry_rank_map]
        is_top20_industry = any(r <= 20 for r in ranks) if ranks else False
        glow_style = (
            "box-shadow:0 0 8px 2px #FF4B4B; border:1px solid #FF4B4B;"
            if is_top20_industry #and sym in (ma50bounce_all | cloudwick_all | cloud21ema_all)
            else ""
        )

        # Priority: orange (50ma_bounce) > aqua (21ema_wick) > purple (21ema_cloud) > default
        if sym in ma50bounce_all:
            html_leader += (
                f'<div class="ticker-badge orange-badge" style="{glow_style}">'
                f'{dot}'
                f'<span style="color:#111111;font-weight:bold;">{sym}</span>'
                f'<span style="color:#004d26;font-weight:bold;">{streak_html}</span>'
                f'</div>'
            )
        elif sym in cloudwick_all:
            html_leader += (
                f'<div class="ticker-badge aqua-badge" style="{glow_style}">'
                f'{dot}'
                f'<span style="color:#000000;font-weight:bold;">{sym}</span>'
                f'<span style="color:#0f766e;font-weight:bold;">{streak_html}</span>'
                f'</div>'
            )
        elif sym in cloud21ema_all:
            html_leader += (
                f'<div class="ticker-badge purple-badge" style="{glow_style}">'
                f'{dot}'
                f'<span style="color:#000000;font-weight:bold;">{sym}</span>'
                f'<span style="color:#7e22ce;font-weight:bold;">{streak_html}</span>'
                f'</div>'
            )
        else:
            html_leader += (
                f'<div class="ticker-badge" style="{glow_style}">'
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
if not leader_hist.empty:
    # 1. Create a temporary copy to prevent altering your original global dataframe
    chart_df = leader_hist.copy()
    
    # 2. Determine if the most recent row (today) holds the absolute maximum value
    today_value = chart_df["Leader Count"].iloc[-1]
    max_value = chart_df["Leader Count"].max()
    min_value = chart_df["Leader Count"].min()

    # NEW: statistical outliers (>=2 std dev above mean) turn red
    mean_val = chart_df["Leader Count"].mean()
    std_val  = chart_df["Leader Count"].std(ddof=1)
    if std_val and std_val > 0:
        z_scores = (chart_df["Leader Count"] - mean_val) / std_val
    else:
        z_scores = pd.Series(0, index=chart_df.index)
    chart_df["Bar_Color"] = "#29B5E8"
    chart_df.loc[z_scores >= 2, "Bar_Color"] = "#FF4B4B"
    
    # 3. Add a explicit 'Bar_Color' column to your dataframe
    if today_value == max_value or today_value == min_value:
        # Define base color array, then override the last row (today) with your accent color
        chart_df.iloc[-1, chart_df.columns.get_loc("Bar_Color")] = "#FF4B4B"
    # else: leave as-is (already blue, or red from z-score outlier check above)

    # 4. Render chart mapping color directly to the new dataframe column
    st.bar_chart(
        data=chart_df,
        x="Date",
        y="Leader Count",
        color="Bar_Color",  # Direct Streamlit to read colors line-by-line from this column
        use_container_width=True
    )

def generate_leader_ai_analysis(leader_list, industry_counts, ticker_industry, rs_nh_list, quad_points=None):
    sorted_industries = sorted(industry_counts.items(), key=lambda x: -x[1])

    # ── NEW: industry -> tickers, so prompt can show bracketed lists ──
    industry_ticker_map = {}
    for t, inds in ticker_industry.items():
        for ind in inds:
            industry_ticker_map.setdefault(ind, []).append(t)

    top_industries_str = "\n".join(
        f"  - {ind} ({', '.join(sorted(industry_ticker_map.get(ind, [])))}): {cnt} leader(s)"
        for ind, cnt in sorted_industries[:10]
    )

    tagged_leaders = []
    for t in leader_list:
        tag  = " [BLUE DOT]" if t in rs_nh_list else ""
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

Industry concentration (with matching tickers):
{top_industries_str}

{quad_summary}

Note: [BLUE DOT] = stock hitting a 250-day RS high right now (strongest near-term momentum).

IMPORTANT FORMATTING RULE: Whenever you mention an industry or sector name anywhere in your response, immediately follow it with the matching tickers in brackets, exactly like this: "Aerospace/Defense (LMT, NOC, SHLD, ITA, XAR)". Use ONLY the tickers listed next to that industry above — do not add or invent tickers.

Respond with EXACTLY these 5 lines, each starting with the bolded label below followed by a colon, then the content on the SAME line. Do not add extra bullets, headers, or commentary outside these 5 lines. Do not rename or reorder the labels.

**Sector Leadership**: Which 2-3 industries dominate the RS leader list and what does that signal?
**Blue Dot Themes**: Are the BLUE DOT stocks concentrated in any particular theme?
**Divergence & Rotation**: Any notable divergence or rotation worth flagging?
**Quadrant Map Insight**: Which quadrant has the most concentration, and what does the Strong vs Improving vs Weakening split suggest about market rotation right now?
**Tactical Takeaway**: One-line tactical takeaway for a swing trader.

Be direct, use industry names with the bracket format above, no fluff. Each line's content should be 1-2 sentences max.
"""

    TRANSIENT_CODES = [
        "503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED",
        "quota", "overloaded", "high demand", "rate_limit",
        "capacity", "timeout", "502", "529",
    ]

    def is_transient(error_str):
        return any(code.lower() in error_str.lower() for code in TRANSIENT_CODES)

    failures = {}

    # ── Provider 1: Gemini ────────────────────────────────────────────────
    gemini_attempts = [
        ("Gemini 2.5 Flash", st.secrets.get("GEMINI_API_KEY"),   "gemini-2.5-flash"),
        ("Gemini 3.5 Flash", st.secrets.get("GEMINI_API_KEY_2"), "gemini-3.5-flash"),
    ]
    for gemini_label, gemini_key, gemini_model in gemini_attempts:
        if not gemini_key:
            failures[gemini_label] = "No key in secrets"
            continue
        try:
            from google import genai as google_genai
            client = google_genai.Client(api_key=gemini_key)
            response = client.models.generate_content(model=gemini_model, contents=prompt)
            return f"🟦 **{gemini_label}**\n\n{response.text}"
        except Exception as e:
            err = str(e)
            if not is_transient(err):
                failures[gemini_label] = err[:120]
                continue
            failures[gemini_label] = err[:120]

    # ── Provider 2: Groq ──────────────────────────────────────────────────
    # Free tier: llama-3.3-70b-versatile, mixtral-8x7b-32768, gemma2-9b-it
    # Docs: console.groq.com/docs/openai
    groq_key = st.secrets.get("GROQ_API_KEY")
    if groq_key:
        try:
            from openai import OpenAI as OpenAIClient
            groq_client = OpenAIClient(
                api_key=groq_key,
                base_url="https://api.groq.com/openai/v1",
            )
            completion = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "You are a concise IBD-style market analyst."},
                    {"role": "user",   "content": prompt},
                ],
                max_tokens=600,
                temperature=0.4,
            )
            result = completion.choices[0].message.content
            summary = format_unavailable_reasons(failures)
            return f"🟧 **Groq / Llama-3.3-70b** *({summary})*\n\n{result}"
        except Exception as e:
            err = str(e)
            if not is_transient(err):
                return f"🔴 **Groq error (non-transient)**\n\n{err}"
            failures["Groq"] = err[:120]
    else:
        failures["Groq"] = "No GROQ_API_KEY in secrets"

    # ── Provider 3: OpenRouter ────────────────────────────────────────────
    # Pay-per-token but has generous free models (look for ":free" suffix).
    # Free models as of 2025: meta-llama/llama-3.1-8b-instruct:free,
    #   mistralai/mistral-7b-instruct:free, google/gemma-3-27b-it:free
    # Docs: openrouter.ai/docs
    openrouter_key = st.secrets.get("OPENROUTER_API_KEY")
    if openrouter_key:
        try:
            from openai import OpenAI as OpenAIClient
            or_client = OpenAIClient(
                api_key=openrouter_key,
                base_url="https://openrouter.ai/api/v1",
                default_headers={
                    "HTTP-Referer": "https://your-app-name.streamlit.app",  # update this
                    "X-Title": "Theme Tracker",
                },
            )
            completion = or_client.chat.completions.create(
                model="meta-llama/llama-3.1-8b-instruct:free",
                messages=[
                    {"role": "system", "content": "You are a concise IBD-style market analyst."},
                    {"role": "user",   "content": prompt},
                ],
                max_tokens=600,
                temperature=0.4,
            )
            result = completion.choices[0].message.content
            summary = format_unavailable_reasons(failures)
            return f"🟣 **OpenRouter / Llama-3.1-8b** *({summary})*\n\n{result}"
        except Exception as e:
            err = str(e)
            if not is_transient(err):
                return f"🔴 **OpenRouter error (non-transient)**\n\n{err}"
            failures["OpenRouter"] = err[:120]
    else:
        failures["OpenRouter"] = "No OPENROUTER_API_KEY in secrets"

    # ── Provider 4: GitHub Models ─────────────────────────────────────────
    # Free while in preview (as of 2025). Uses OpenAI SDK + Azure endpoint.
    # Available models: gpt-4o, gpt-4o-mini, Phi-3, Mistral-large, Llama etc.
    # Full list: github.com/marketplace/models
    github_token = st.secrets.get("GITHUB_MODELS_TOKEN")
    if github_token:
        try:
            from openai import OpenAI as OpenAIClient
            github_client = OpenAIClient(
                api_key=github_token,
                base_url="https://models.inference.ai.azure.com",
            )
            completion = github_client.chat.completions.create(
                model="gpt-4o-mini",           # or "Meta-Llama-3.1-70B-Instruct"
                messages=[
                    {"role": "system", "content": "You are a concise IBD-style market analyst."},
                    {"role": "user",   "content": prompt},
                ],
                max_tokens=600,
                temperature=0.4,
            )
            result = completion.choices[0].message.content
            summary = format_unavailable_reasons(failures)
            return f"⬜ **GitHub Models / gpt-4o-mini** *({summary})*\n\n{result}"
        except Exception as e:
            err = str(e)
            if not is_transient(err):
                return f"🔴 **GitHub Models error (non-transient)**\n\n{err}"
            failures["GitHub Models"] = err[:120]
    else:
        failures["GitHub Models"] = "No GITHUB_MODELS_TOKEN in secrets"

    # ── All providers failed ──────────────────────────────────────────────
    failure_lines = "\n".join(f"- {p}: {r}" for p, r in failures.items())
    return (
        "🔴 **All AI providers failed**\n\n"
        f"{failure_lines}"
    )

def generate_group_theme_insight(tickers, section_title, session_key, extra_note="", industries_dict=None):
    if industries_dict is None:
        industries_dict = INDUSTRIES
    if not tickers:
        return None

    industry_counts, ticker_industry = build_leader_industry_map(tickers, industries_dict)
    sorted_industries = sorted(industry_counts.items(), key=lambda x: -x[1])

    # ── NEW: build industry -> matching tickers map, so we can show
    # "Industry Name (TICK1, TICK2)" directly in the prompt itself ──
    industry_ticker_map = {}
    for t, inds in ticker_industry.items():
        for ind in inds:
            industry_ticker_map.setdefault(ind, []).append(t)

    top_industries_str = "\n".join(
        f"  - {ind} ({', '.join(sorted(industry_ticker_map.get(ind, [])))}): {cnt}"
        for ind, cnt in sorted_industries[:8]
    ) or "  - (no industry matches found)"

    tagged = [f"{t} ({', '.join(ticker_industry.get(t, ['?']))})" for t in tickers[:40]]
    tickers_str = "\n".join(tagged)

    prompt = f"""
You are a concise IBD-style market analyst. Below is a list of stocks that just triggered the "{section_title}" screen{(' — ' + extra_note) if extra_note else ''}.

Tickers ({len(tickers)} total) with industry group:
{tickers_str}

Industry concentration (with matching tickers):
{top_industries_str}

IMPORTANT FORMATTING RULE: Whenever you mention an industry or sector name anywhere in your response, immediately follow it with the matching tickers in brackets, exactly like this: "Aerospace/Defense (LMT, NOC, SHLD, ITA, XAR)". Use ONLY the tickers listed next to that industry above — do not add or invent tickers.

Respond with EXACTLY these 3 lines, each starting with the bolded label below followed by a colon, then the content on the SAME line. Do not add extra bullets, headers, or commentary outside these 3 lines. Do not rename or reorder the labels.

**Common Theme**: Is there a common theme, sector, or sub-industry driving this list right now?
**Standout Industries**: Which 1-2 industries/sub-groups stand out, and what might that imply?
**Tactical Takeaway**: One-line tactical takeaway for a swing trader watching this screen.

Be direct, name industries/tickers explicitly with the bracket format above, no fluff, no repeating the prompt. Each line's content should be 1-2 sentences max.
"""

    TRANSIENT_CODES = ["503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED", "quota",
                        "overloaded", "high demand", "rate_limit", "capacity", "timeout", "502", "529"]
    def is_transient(e):
        return any(c.lower() in e.lower() for c in TRANSIENT_CODES)

    failures = {}

    # ── Gemini ──
    gemini_attempts = [
        ("Gemini 2.5 Flash", st.secrets.get("GEMINI_API_KEY"),   "gemini-2.5-flash"),
        ("Gemini 3.5 Flash", st.secrets.get("GEMINI_API_KEY_2"), "gemini-3.5-flash"),
    ]
    for gemini_label, gemini_key, gemini_model in gemini_attempts:
        if not gemini_key:
            failures[gemini_label] = "No key in secrets"
            continue
        try:
            from google import genai as google_genai
            client = google_genai.Client(api_key=gemini_key)
            response = client.models.generate_content(model=gemini_model, contents=prompt)
            return f"🟦 **{gemini_label}**\n\n{response.text}"
        except Exception as e:
            err = str(e)
            if not is_transient(err):
                failures[gemini_label] = err[:120]
                continue
            failures[gemini_label] = err[:120]

    # ── Groq ──
    groq_key = st.secrets.get("GROQ_API_KEY")
    if groq_key:
        try:
            from openai import OpenAI as OpenAIClient
            groq_client = OpenAIClient(api_key=groq_key, base_url="https://api.groq.com/openai/v1")
            completion = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "system", "content": "You are a concise IBD-style market analyst."},
                          {"role": "user", "content": prompt}],
                max_tokens=350, temperature=0.4,
            )
            summary = format_unavailable_reasons(failures)
            return f"🟧 **Groq / Llama-3.3-70b** *({summary})*\n\n{completion.choices[0].message.content}"
        except Exception as e:
            err = str(e)
            if not is_transient(err):
                return f"🔴 **Groq error (non-transient)**\n\n{err}"
            failures["Groq"] = err[:120]
    else:
        failures["Groq"] = "No GROQ_API_KEY"

    # ── OpenRouter ──
    openrouter_key = st.secrets.get("OPENROUTER_API_KEY")
    if openrouter_key:
        try:
            from openai import OpenAI as OpenAIClient
            or_client = OpenAIClient(
                api_key=openrouter_key, base_url="https://openrouter.ai/api/v1",
                default_headers={"HTTP-Referer": "https://your-app-name.streamlit.app", "X-Title": "Theme Tracker"},
            )
            completion = or_client.chat.completions.create(
                model="meta-llama/llama-3.1-8b-instruct:free",
                messages=[{"role": "system", "content": "You are a concise IBD-style market analyst."},
                          {"role": "user", "content": prompt}],
                max_tokens=350, temperature=0.4,
            )
            summary = format_unavailable_reasons(failures)
            return f"🟣 **OpenRouter / Llama-3.1-8b** *({summary})*\n\n{completion.choices[0].message.content}"
        except Exception as e:
            err = str(e)
            if not is_transient(err):
                return f"🔴 **OpenRouter error (non-transient)**\n\n{err}"
            failures["OpenRouter"] = err[:120]
    else:
        failures["OpenRouter"] = "No OPENROUTER_API_KEY"

    # ── GitHub Models ──
    github_token = st.secrets.get("GITHUB_MODELS_TOKEN")
    if github_token:
        try:
            from openai import OpenAI as OpenAIClient
            github_client = OpenAIClient(api_key=github_token, base_url="https://models.inference.ai.azure.com")
            completion = github_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": "You are a concise IBD-style market analyst."},
                          {"role": "user", "content": prompt}],
                max_tokens=350, temperature=0.4,
            )
            summary = format_unavailable_reasons(failures)
            return f"⬜ **GitHub Models / gpt-4o-mini** *({summary})*\n\n{completion.choices[0].message.content}"
        except Exception as e:
            err = str(e)
            if not is_transient(err):
                return f"🔴 **GitHub Models error (non-transient)**\n\n{err}"
            failures["GitHub Models"] = err[:120]
    else:
        failures["GitHub Models"] = "No GITHUB_MODELS_TOKEN"

    failure_lines = "\n".join(f"- {p}: {r}" for p, r in failures.items())
    return f"🔴 **All AI providers failed**\n\n{failure_lines}"


def render_group_ai_insight(tickers, section_title, session_key, extra_note="", industries_dict=None):
    """
    Drop-in renderer: call right after any badge-list block.
    Caches per section_key in session_state so it only re-calls the AI when
    that section's ticker list actually changes; includes a manual retry button.
    """
    if not tickers:
        return

    ticker_key = f"{session_key}_ai_key"
    result_key = f"{session_key}_ai_result"
    current_sig = str(sorted(tickers))
    
    st.write("")
    force = st.button("🔄 AI Insight", key=f"retry_{session_key}")

    if force or st.session_state.get(ticker_key) != current_sig:
        with st.spinner(f"Analyzing {section_title} theme..."):
            result = timed(
                f"generate_group_theme_insight[{section_title}]",
                generate_group_theme_insight,
                tickers, section_title, session_key, extra_note, industries_dict
            )
        if result:
            st.session_state[result_key] = result
            st.session_state[ticker_key] = current_sig

    if result_key in st.session_state:
        industries_seen = list(build_leader_industry_map(tickers, industries_dict or INDUSTRIES)[0].keys())
        render_ai_points_table(
            st.session_state[result_key], tickers=tickers, industries=industries_seen
        )

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
        df_leaders_summary = pd.DataFrame(summary_rows)

        def highlight_top3_lime(row):
            if row.name < 3:
                return ["background-color: #90EE90; color: #000000; font-weight: bold;"] * len(row)
            return [""] * len(row)

        TOP_N_DEFAULT = 5

        # ── Default: top 5 rows only ─────────────────────────────────────────
        df_top5 = df_leaders_summary.head(TOP_N_DEFAULT)
        styled_top5_df = df_top5.style.apply(highlight_top3_lime, axis=1)

        st.dataframe(
            styled_top5_df,
            use_container_width=False,
            width=300,
            hide_index=True,
            height=36 * len(df_top5) + 38,
            column_config={
                "Leaders": st.column_config.Column()
            }
        )
    st.markdown(
        "<style>div[data-testid='stMetricLabel']{font-size:11px !important;}"
        "div[data-testid='stMetricValue']{font-size:26px !important;}</style>",
        unsafe_allow_html=True
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
        render_ai_points_table(
            st.session_state["leader_ai_result"],
            tickers=leader_list,
            industries=list(industry_counts.keys())
        )

# ============================================================
# TRUE MARKET LEADER (TML) — healthyPct >= 69.5% Scan
# Ported from TradingView "Score" indicator's TML logic.
# Reuses the same 9-component score as Change/Breakdown of
# Character (score5/Darvas-streak omitted; score6/score7 lite).
# Note: Pine's "[X days ago]" label is tied to a separate
# is_leader (RS-leader) state, not this threshold — omitted here.
# ============================================================
@st.cache_data(ttl=3600)
def compute_true_market_leaders(stocks_list, ticker_dfs, benchmark_df_input,
                                  lookback_period=126, threshold=69.5):
    """
    ...
    Returns: today_matches (sorted), yest_matches (sorted), healthy_pct_map {ticker: pct}, history_df
    """
    today_matches = []
    yest_matches = []
    healthy_pct_map = {}
    all_flag_series = []

    weights = np.arange(1, lookback_period + 1)
    weight_sum = weights.sum()

    def _wma(arr):
        return np.dot(arr, weights) / weight_sum

    excluded_etfs = {"IWM", "QQQ", "SPY"}
    for ticker in stocks_list:
        try:
            if ticker in excluded_etfs:
                continue
            df = ticker_dfs.get(ticker)
            if df is None or len(df) < 260 + lookback_period:
                continue

            close = df['Close']; high = df['High']; low = df['Low']

            rs = close / benchmark_df_input['Close']
            if rs.dropna().empty:
                continue

            ema126 = close.ewm(span=126, adjust=False).mean()
            r = {sp: rs.ewm(span=sp, adjust=False).mean() for sp in [21, 42, 63, 72, 84, 126, 147, 168]}

            stage1_cond  = (rs >= r[84]) & (rs < r[126])
            stage3_cond  = (
                (rs < r[42]) & (rs >= r[72]) & (rs >= r[84]) & (rs >= r[126])
                & ((r[42] > r[63]) | (rs < r[63])) & (r[63] > r[126]) & (close >= ema126)
            )
            stage2a_cond = (
                (rs >= r[168]) & (rs >= r[147]) & (rs >= r[126])
                & (close >= ema126) & ((r[21] >= r[42]) | (r[42] >= r[63]))
            )
            stage2b_cond = (rs >= r[126]) & (close >= ema126) & ((r[21] >= r[42]) | (r[42] >= r[63]))
            stage2_cond  = (~stage1_cond & ~stage3_cond & (stage2a_cond | stage2b_cond))

            rsMA21  = rs.ewm(span=21, adjust=False).mean()
            ema21   = close.ewm(span=21, adjust=False).mean()
            sma50   = close.rolling(50).mean()
            sma200  = close.rolling(200).mean()
            low14   = low.rolling(14).min().shift(1)
            ema50t  = close.ewm(span=50, adjust=False).mean()
            ema100t = close.ewm(span=100, adjust=False).mean()

            gap_down_evt       = (high < low.shift(1))
            gap_down_pct       = ((close.shift(1) - close) / close.shift(1) * 100).where(gap_down_evt)
            gap_down_qualified = gap_down_evt & (gap_down_pct >= 3)
            recent_gap_down    = gap_down_qualified.rolling(10, min_periods=1).max().fillna(0).astype(bool)

            pct_chg = close.pct_change() * 100
            win = min(220, len(pct_chg))
            biggest_drop = pct_chg.rolling(window=win, min_periods=20).min()
            biggest_up   = pct_chg.rolling(window=win, min_periods=20).max()

            high252 = high.rolling(252, min_periods=50).max()
            pct_from_high = (close - high252) / high252 * 100

            s1  = (rs > rsMA21).fillna(False).astype(int) * 10
            s2  = stage2_cond.fillna(False).astype(int) * 10
            s3  = (close > ema21).fillna(False).astype(int) * 10
            s4  = (close > sma50).fillna(False).astype(int) * 10
            s6  = (~(close < low14).fillna(False)).astype(int) * 10
            s7  = (~recent_gap_down).astype(int) * 10
            s8  = (~(biggest_up < -biggest_drop).fillna(False)).astype(int) * 10
            s9  = (~(pct_from_high < -25).fillna(False)).astype(int) * 10
            s10 = (ema50t >= ema100t).fillna(False).astype(int) * 10

            score = s1 + s2 + s3 + s4 + s6 + s7 + s8 + s9 + s10
            healthy_series = (score >= 80).astype(float) * 100.0

            if len(healthy_series) < lookback_period:
                continue

            healthy_pct_series = healthy_series.rolling(lookback_period).apply(_wma, raw=True)

            today_pct = healthy_pct_series.iloc[-1]
            if pd.isna(today_pct):
                continue

            healthy_pct_map[ticker] = round(float(today_pct), 1)

            latest_above_ma50 = close.iloc[-1] > sma50.iloc[-1]
            latest_above_ma200 = close.iloc[-1] > sma200.iloc[-1]
            if today_pct >= threshold and latest_above_ma50 and latest_above_ma200:
                today_matches.append(ticker)

            # ── Yesterday check (mirrors today, shifted one bar back) ──
            if len(healthy_pct_series) >= 2:
                yest_pct = healthy_pct_series.iloc[-2]
                if pd.notna(yest_pct) and len(sma50) >= 2 and len(sma200) >= 2 and len(close) >= 2:
                    yest_above_ma50 = close.iloc[-2] > sma50.iloc[-2]
                    yest_above_ma200 = close.iloc[-2] > sma200.iloc[-2]
                    if yest_pct >= threshold and yest_above_ma50 and yest_above_ma200:
                        yest_matches.append(ticker)

            all_flag_series.append(
                (healthy_pct_series >= threshold).astype(int).tail(60).rename(ticker)
            )

        except Exception:
            continue

    history_df = pd.DataFrame()
    if all_flag_series:
        combined = pd.concat(all_flag_series, axis=1).fillna(0)
        daily_counts = combined.sum(axis=1)
        history_df = daily_counts.reset_index()
        history_df.columns = ["Date", "TML Count"]
        history_df["Date"] = pd.to_datetime(history_df["Date"]).dt.strftime("%Y-%m-%d")

    return sorted(today_matches), sorted(yest_matches), healthy_pct_map, history_df


# ── Render section — append at the very bottom of the dashboard ────────────
st.markdown("---")

with st.spinner("Scanning for True Market Leaders (healthyPct >= 69.5%)..."):
    tml_list, tml_yest, tml_pct_map, tml_hist = timed(
        "compute_true_market_leaders",
        compute_true_market_leaders,
        stocks_tuple, ticker_dfs_shared, benchmark_df_shared
    )

tml_count = len(tml_list)
tml_count_color = "#FF4B4B" if tml_count == 0 else "#FFFFFF"
st.markdown(f"#### 👑 True Market Leader = A+ Leader on weakness is a gift (<span style='color:{tml_count_color};'>{tml_count}</span>)", unsafe_allow_html=True)

if tml_list or tml_yest:
    tml_industry_counts, tml_ticker_industry = build_leader_industry_map(tml_list, INDUSTRIES)

    html_tml = ""
    for sym in tml_list:  # alphabetical
        industries = tml_ticker_industry.get(sym, [])
        ranks = [industry_rank_map[ind] for ind in industries if ind in industry_rank_map]
        is_top20_industry = any(r <= 20 for r in ranks) if ranks else False
        glow_style = (
            "box-shadow:0 0 8px 2px #FF4B4B; border:1px solid #FF4B4B;"
            if is_top20_industry else ""
        )
        pct_val = tml_pct_map.get(sym, 0)
        suffix = f"{pct_val:.0f}%"
        html_tml += setup_badge(
            sym,
            is_new=(sym not in tml_yest),
            extra_style=glow_style,
            extra_suffix=suffix,
            extra_suffix_color="#B8860B",
        )

    removed_tml = [sym for sym in tml_yest if sym not in tml_list]
    for sym in sorted(removed_tml):
        html_tml += f'<div class="ticker-badge removed-badge">{sym}</div>'

    st.markdown(html_tml, unsafe_allow_html=True)

    render_group_ai_insight(
        tml_list,
        "True Market Leader (healthyPct >= 69.5%)",
        "true_market_leader",
        extra_note="the stock's composite health score has been at or above 90 (out of 90) for a weighted-majority of the trailing 126 trading days, indicating sustained multi-month technical leadership rather than a one-day spike"
    )
else:
    st.info("No active True Market Leaders discovered.")

st.write("")
if not tml_hist.empty:
    chart_df_tml = tml_hist.copy()
    today_tml = chart_df_tml["TML Count"].iloc[-1]
    max_tml = chart_df_tml["TML Count"].max()
    min_tml = chart_df_tml["TML Count"].min()

    chart_df_tml["Bar_Color"] = "#29B5E8"

    # NEW: statistical outliers (>=2 std dev above mean) turn red
    mean_tml = chart_df_tml["TML Count"].mean()
    std_tml  = chart_df_tml["TML Count"].std(ddof=1)
    if std_tml and std_tml > 0:
        z_scores_tml = (chart_df_tml["TML Count"] - mean_tml) / std_tml
    else:
        z_scores_tml = pd.Series(0, index=chart_df_tml.index)
    chart_df_tml.loc[z_scores_tml >= 2, "Bar_Color"] = "#FF4B4B"

    if today_tml == min_tml:
        chart_df_tml.iloc[-1, chart_df_tml.columns.get_loc("Bar_Color")] = "#FF4B4B"
    elif today_tml == max_tml:
        chart_df_tml.iloc[-1, chart_df_tml.columns.get_loc("Bar_Color")] = "#FFD700"

    st.bar_chart(
        data=chart_df_tml,
        x="Date",
        y="TML Count",
        color="Bar_Color",
        use_container_width=True
    )

st.markdown("---")

# --- 2. TIGHT PPP (Full Horizontal Row Below Two Botak) ---
st.markdown(f"#### 📉 PPP = Opportunity ({len(ppp_list)})")

if ppp_list or ppp_yest:
    # ── NEW: map to industries for top-20 glow check ──
    ppp_industry_counts, ppp_ticker_industry = build_leader_industry_map(ppp_list, INDUSTRIES)

    # ── Badge row ─────────────────────────────────────────────────────────
    html_p = ""
    for sym in ppp_list:
        industries = ppp_ticker_industry.get(sym, [])
        ranks = [industry_rank_map[ind] for ind in industries if ind in industry_rank_map]
        is_top20_industry = any(r <= 20 for r in ranks) if ranks else False
        glow_style = (
            "box-shadow:0 0 8px 2px #FF4B4B; border:1px solid #FF4B4B;"
            if is_top20_industry else ""
        )
        html_p += setup_badge(sym, is_new=(sym not in ppp_yest), extra_style=glow_style)

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
    # ── NEW: map to industries for top-20 glow check ──
    rsnh_industry_counts, rsnh_ticker_industry = build_leader_industry_map(rs_nh_b4_today, INDUSTRIES)

    html_rsnh = ""
    for sym in rs_nh_b4_today:
        industries = rsnh_ticker_industry.get(sym, [])
        ranks = [industry_rank_map[ind] for ind in industries if ind in industry_rank_map]
        is_top20_industry = any(r <= 20 for r in ranks) if ranks else False
        glow_style = (
            "box-shadow:0 0 8px 2px #FF4B4B; border:1px solid #FF4B4B;"
            if is_top20_industry else ""
        )
        html_rsnh += setup_badge(sym, is_new=(sym not in rs_nh_b4_yest), extra_style=glow_style)

    removed_rsnh = [sym for sym in rs_nh_b4_yest if sym not in rs_nh_b4_today]
    for sym in removed_rsnh:
        html_rsnh += f'<div class="ticker-badge removed-badge">{sym}</div>'

    st.markdown(html_rsnh, unsafe_allow_html=True)

    render_group_ai_insight(
        rs_nh_b4_today,
        "RS New High Before Price (opportunity)",
        "rs_nh_b4_price",
        extra_note="the stock's relative strength vs the S&P 500 just hit a 20-day high, but the stock's own price high has not yet reached its 20-day high — RS is leading price, often an early breakout precursor"
    )
else:
    st.info("No active setups discovered.")

#st.markdown("<br>", unsafe_allow_html=True) # Spacer
st.markdown("---")

# --- GAPPER SECTION ---
st.markdown(f"#### 🚀 Gapper Earning Drift = Opportunity ({len(gapper_list)})")

if gapper_list or gapper_yest:
    # ── NEW: map to industries for top-20 glow check ──
    gapper_industry_counts, gapper_ticker_industry = build_leader_industry_map(gapper_list, INDUSTRIES)

    # ── Badge row ─────────────────────────────────────────────────────────
    html_g = ""
    for sym in gapper_list:
        industries = gapper_ticker_industry.get(sym, [])
        ranks = [industry_rank_map[ind] for ind in industries if ind in industry_rank_map]
        is_top20_industry = any(r <= 20 for r in ranks) if ranks else False
        glow_style = (
            "box-shadow:0 0 8px 2px #FF4B4B; border:1px solid #FF4B4B;"
            if is_top20_industry else ""
        )
        html_g += setup_badge(sym, is_new=(sym not in gapper_yest), extra_style=glow_style)

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

    render_group_ai_insight(
        gapper_list,
        "Gapper Earning Drift (opportunity)",
        "gapper_drift",
        extra_note="the stock gapped up 10%+ (often on earnings) and that gap remains unfilled within the last 30 trading days, suggesting continuation/drift after a strong catalyst"
    )

else:
    st.info("No active setups discovered.")

with st.spinner("Scanning for Gapper History..."):
    gapper_hist = timed("compute_gapper_history", compute_gapper_history, stocks_tuple, ticker_dfs_shared)

st.write("")
if not gapper_hist.empty:
    chart_df_g = gapper_hist.copy().reset_index(drop=True)

    today_g = chart_df_g["Gapper Count"].iloc[-1]
    max_g   = chart_df_g["Gapper Count"].max()
    min_g   = chart_df_g["Gapper Count"].min()

    # Default: every bar blue
    chart_df_g["Bar_Color"] = "#29B5E8"

    # NEW: statistical outliers (>=2 std dev above mean) turn red
    mean_g = chart_df_g["Gapper Count"].mean()
    std_g  = chart_df_g["Gapper Count"].std(ddof=1)
    if std_g and std_g > 0:
        z_scores_g = (chart_df_g["Gapper Count"] - mean_g) / std_g
    else:
        z_scores_g = pd.Series(0, index=chart_df_g.index)
    chart_df_g.loc[z_scores_g >= 2, "Bar_Color"] = "#FF4B4B"

    # Latest bar turns red if today is either the highest OR the lowest
    # value across the whole 60-day window
    if today_g == max_g or today_g == min_g:
        chart_df_g.iloc[-1, chart_df_g.columns.get_loc("Bar_Color")] = "#FF4B4B"

    st.bar_chart(
        data=chart_df_g,
        x="Date",
        y="Gapper Count",
        color="Bar_Color",
        use_container_width=True
    )

@st.cache_data(ttl=3600)
def compute_early_bull(stocks_list, ticker_dfs, benchmark_df_input):
    """
    Python port of the Pine Script stage1to2AlertCond block:
      - Detect Stage 1->2 or Stage 4->2 transitions (vectorized across full history)
      - Track the high price at the most recent transition bar (var float behavior)
      - stage1to2Recent30: a transition occurred within the last 30 bars
      - stage1to2PriceAbove: current close > that transition bar's high
      - stage1to2AlertCond: recent30 AND priceAbove AND currently in Stage 2
    Then combine with cond1..cond4 (ADR%, ATR21_R, ATR50_R, EMA21-low distance%)
    to find "Early Bull" candidates.
    """
    matches = []
    if benchmark_df_input is None or benchmark_df_input.empty:
        return matches

    bm_idx = benchmark_df_input.index.tz_localize(None) if benchmark_df_input.index.tz is not None else benchmark_df_input.index
    bm_aligned = benchmark_df_input.copy()
    bm_aligned.index = bm_idx

    for ticker in stocks_list:
        try:
            df = ticker_dfs.get(ticker)
            if df is None or len(df) < 260:
                continue

            df_idx = df.index.tz_localize(None) if df.index.tz is not None else df.index
            df_aligned = df.copy()
            df_aligned.index = df_idx

            combined = pd.merge(
                df_aligned[['Close', 'Open', 'High', 'Low']],
                bm_aligned[['Close']].rename(columns={'Close': 'Close_bench'}),
                left_index=True, right_index=True, how='inner'
            )
            if len(combined) < 260:
                continue

            close = combined['Close']; open_ = combined['Open']
            high  = combined['High'];  low   = combined['Low']

            ema126 = df_aligned['Close'].ewm(span=126, adjust=False).mean().reindex(combined.index, method='ffill')
            rs = close / combined['Close_bench']

            ema_spans = [21, 42, 63, 72, 84, 126, 147, 168]
            r = {s: rs.ewm(span=s, adjust=False).mean() for s in ema_spans}

            stage1_cond = (rs >= r[84]) & (rs < r[126])
            stage3_cond = (
                (rs < r[42]) & (rs >= r[72]) & (rs >= r[84]) & (rs >= r[126])
                & ((r[42] > r[63]) | (rs < r[63])) & (r[63] > r[126]) & (close >= ema126)
            )
            stage2a_cond = (
                (rs >= r[168]) & (rs >= r[147]) & (rs >= r[126])
                & (close >= ema126) & ((r[21] >= r[42]) | (r[42] >= r[63]))
            )
            stage2b_cond = (rs >= r[126]) & (close >= ema126) & ((r[21] >= r[42]) | (r[42] >= r[63]))
            stage4_cond = ((rs < r[63]) & (rs < r[126])) | ((r[63] < r[126]) & (rs < r[126]))

            # Resolve final stage number per bar (mirrors Pine's if/elif priority order,
            # same simplified mapping already used in compute_stage_history)
            stage_num = pd.Series(0, index=combined.index)
            stage_num[stage1_cond] = 1
            remaining = ~stage1_cond
            stage_num[remaining & stage3_cond] = 3
            remaining = remaining & ~stage3_cond
            stage_num[remaining & (stage2a_cond | stage2b_cond)] = 2
            remaining = remaining & ~(stage2a_cond | stage2b_cond)
            stage_num[remaining & stage4_cond] = 4

            # === Stage 1->2 or Stage 4->2 Transition (mirrors Pine stage1to2Transition) ===
            stage_prev = stage_num.shift(1)
            stage1to2Transition = (stage_num == 2) & ((stage_prev == 1) | (stage_prev == 4))

            # Price captured at transition bar (var float behavior -> forward-fill)
            transition_price = high.where(stage1to2Transition)
            stage1to2Price = transition_price.ffill()

            # 30-bar recency + price-above-transition checks
            stage1to2Count30 = stage1to2Transition.astype(int).rolling(30).sum()
            stage1to2Recent30 = stage1to2Count30 >= 1
            stage1to2PriceAbove = stage1to2Price.notna() & (close > stage1to2Price)

            stage1to2AlertCond = stage1to2Recent30 & stage1to2PriceAbove & (stage_num == 2)

            if not bool(stage1to2AlertCond.iloc[-1]):
                continue

            # === cond1..cond4 (ADR%, ATR21_R, ATR50_R, EMA21-low distance%) ===
            sma50 = close.rolling(50).mean()
            ema21_close = close.ewm(span=21, adjust=False).mean()
            ema21_low   = low.ewm(span=21, adjust=False).mean()

            tr = pd.concat([
                high - low,
                (high - close.shift(1)).abs(),
                (low - close.shift(1)).abs()
            ], axis=1).max(axis=1)
            atr = tr.rolling(14).mean()
            atrPercent = (atr / close) * 100

            atr21_R = (((close - ema21_close) / close) * 100) / (atrPercent + 1e-6)
            atr50_R = (((close - sma50) / close) * 100) / (atrPercent + 1e-6)
            emaDistPercent = ((close - ema21_low) / close) * 100

            hl_ratio = high / low
            adrPercent = 100 * (hl_ratio.rolling(20).mean() - 1)

            cond1 = (adrPercent.iloc[-1] >= 2.45) and (adrPercent.iloc[-1] < 8.05)
            cond2 = -0.5 <= atr21_R.iloc[-1] <= 1
            cond3 = 0 <= atr50_R.iloc[-1] <= 3
            cond4 = 0 < emaDistPercent.iloc[-1] <= 8

            if cond1 and cond2 and cond3 and cond4 and close.iloc[-1] >= 20:
                matches.append(ticker)

        except Exception:
            continue

    return sorted(matches)

@st.cache_data(ttl=3600)
def compute_early_bull_no_filter(stocks_list, ticker_dfs, benchmark_df_input):
    """
    Same Stage 1->2 / Stage 4->2 transition detection as compute_early_bull,
    but WITHOUT the cond1-cond4 (ADR%, ATR21_R, ATR50_R, EMA21-low distance%)
    quality filters — returns every ticker meeting the raw stage transition
    condition (still requires close >= 20).
    """
    matches = []
    if benchmark_df_input is None or benchmark_df_input.empty:
        return matches

    bm_idx = benchmark_df_input.index.tz_localize(None) if benchmark_df_input.index.tz is not None else benchmark_df_input.index
    bm_aligned = benchmark_df_input.copy()
    bm_aligned.index = bm_idx

    for ticker in stocks_list:
        try:
            df = ticker_dfs.get(ticker)
            if df is None or len(df) < 260:
                continue

            df_idx = df.index.tz_localize(None) if df.index.tz is not None else df.index
            df_aligned = df.copy()
            df_aligned.index = df_idx

            combined = pd.merge(
                df_aligned[['Close', 'Open', 'High', 'Low']],
                bm_aligned[['Close']].rename(columns={'Close': 'Close_bench'}),
                left_index=True, right_index=True, how='inner'
            )
            if len(combined) < 260:
                continue

            close = combined['Close']
            high  = combined['High']

            ema126 = df_aligned['Close'].ewm(span=126, adjust=False).mean().reindex(combined.index, method='ffill')
            rs = close / combined['Close_bench']

            ema_spans = [21, 42, 63, 72, 84, 126, 147, 168]
            r = {s: rs.ewm(span=s, adjust=False).mean() for s in ema_spans}

            stage1_cond = (rs >= r[84]) & (rs < r[126])
            stage3_cond = (
                (rs < r[42]) & (rs >= r[72]) & (rs >= r[84]) & (rs >= r[126])
                & ((r[42] > r[63]) | (rs < r[63])) & (r[63] > r[126]) & (close >= ema126)
            )
            stage2a_cond = (
                (rs >= r[168]) & (rs >= r[147]) & (rs >= r[126])
                & (close >= ema126) & ((r[21] >= r[42]) | (r[42] >= r[63]))
            )
            stage2b_cond = (rs >= r[126]) & (close >= ema126) & ((r[21] >= r[42]) | (r[42] >= r[63]))
            stage4_cond = ((rs < r[63]) & (rs < r[126])) | ((r[63] < r[126]) & (rs < r[126]))

            stage_num = pd.Series(0, index=combined.index)
            stage_num[stage1_cond] = 1
            remaining = ~stage1_cond
            stage_num[remaining & stage3_cond] = 3
            remaining = remaining & ~stage3_cond
            stage_num[remaining & (stage2a_cond | stage2b_cond)] = 2
            remaining = remaining & ~(stage2a_cond | stage2b_cond)
            stage_num[remaining & stage4_cond] = 4

            stage_prev = stage_num.shift(1)
            stage1to2Transition = (stage_num == 2) & ((stage_prev == 1) | (stage_prev == 4))

            transition_price = high.where(stage1to2Transition)
            stage1to2Price = transition_price.ffill()

            stage1to2Count30 = stage1to2Transition.astype(int).rolling(30).sum()
            stage1to2Recent30 = stage1to2Count30 >= 1
            stage1to2PriceAbove = stage1to2Price.notna() & (close > stage1to2Price)

            stage1to2AlertCond = stage1to2Recent30 & stage1to2PriceAbove & (stage_num == 2)

            if bool(stage1to2AlertCond.iloc[-1]) and close.iloc[-1] >= 20:
                matches.append(ticker)

        except Exception:
            continue

    return sorted(matches)

@st.cache_data(ttl=3600)
def compute_early_bull_combined(stocks_list, ticker_dfs, benchmark_df_input):
    """
    Single-pass version of compute_early_bull + compute_early_bull_no_filter.
    Both scan the same Stage 1->2 / Stage 4->2 transition condition; the only
    difference is the "filtered" list additionally requires cond1-cond4
    (ADR%, ATR21_R, ATR50_R, EMA21-low distance%). Computing the shared
    stage-transition/EMA/RS work once and branching at the end avoids
    doing that work twice per run.

    Returns: (filtered_matches, unfiltered_matches) — both sorted lists.
    """
    filtered = []
    unfiltered = []

    if benchmark_df_input is None or benchmark_df_input.empty:
        return filtered, unfiltered

    bm_idx = benchmark_df_input.index.tz_localize(None) if benchmark_df_input.index.tz is not None else benchmark_df_input.index
    bm_aligned = benchmark_df_input.copy()
    bm_aligned.index = bm_idx

    for ticker in stocks_list:
        try:
            df = ticker_dfs.get(ticker)
            if df is None or len(df) < 260:
                continue

            df_idx = df.index.tz_localize(None) if df.index.tz is not None else df.index
            df_aligned = df.copy()
            df_aligned.index = df_idx

            combined = pd.merge(
                df_aligned[['Close', 'Open', 'High', 'Low']],
                bm_aligned[['Close']].rename(columns={'Close': 'Close_bench'}),
                left_index=True, right_index=True, how='inner'
            )
            if len(combined) < 260:
                continue

            close = combined['Close']; open_ = combined['Open']
            high  = combined['High'];  low   = combined['Low']

            ema126 = df_aligned['Close'].ewm(span=126, adjust=False).mean().reindex(combined.index, method='ffill')
            rs = close / combined['Close_bench']

            ema_spans = [21, 42, 63, 72, 84, 126, 147, 168]
            r = {s: rs.ewm(span=s, adjust=False).mean() for s in ema_spans}

            stage1_cond = (rs >= r[84]) & (rs < r[126])
            stage3_cond = (
                (rs < r[42]) & (rs >= r[72]) & (rs >= r[84]) & (rs >= r[126])
                & ((r[42] > r[63]) | (rs < r[63])) & (r[63] > r[126]) & (close >= ema126)
            )
            stage2a_cond = (
                (rs >= r[168]) & (rs >= r[147]) & (rs >= r[126])
                & (close >= ema126) & ((r[21] >= r[42]) | (r[42] >= r[63]))
            )
            stage2b_cond = (rs >= r[126]) & (close >= ema126) & ((r[21] >= r[42]) | (r[42] >= r[63]))
            stage4_cond = ((rs < r[63]) & (rs < r[126])) | ((r[63] < r[126]) & (rs < r[126]))

            # Resolve final stage number per bar
            stage_num = pd.Series(0, index=combined.index)
            stage_num[stage1_cond] = 1
            remaining = ~stage1_cond
            stage_num[remaining & stage3_cond] = 3
            remaining = remaining & ~stage3_cond
            stage_num[remaining & (stage2a_cond | stage2b_cond)] = 2
            remaining = remaining & ~(stage2a_cond | stage2b_cond)
            stage_num[remaining & stage4_cond] = 4

            # === Stage 1->2 or Stage 4->2 Transition ===
            stage_prev = stage_num.shift(1)
            stage1to2Transition = (stage_num == 2) & ((stage_prev == 1) | (stage_prev == 4))

            transition_price = high.where(stage1to2Transition)
            stage1to2Price = transition_price.ffill()

            stage1to2Count30 = stage1to2Transition.astype(int).rolling(30).sum()
            stage1to2Recent30 = stage1to2Count30 >= 1
            stage1to2PriceAbove = stage1to2Price.notna() & (close > stage1to2Price)

            stage1to2AlertCond = stage1to2Recent30 & stage1to2PriceAbove & (stage_num == 2)

            if not bool(stage1to2AlertCond.iloc[-1]):
                continue
            if close.iloc[-1] < 20:
                continue

            # Unfiltered match confirmed
            unfiltered.append(ticker)

            # === cond1..cond4 (ADR%, ATR21_R, ATR50_R, EMA21-low distance%) ===
            sma50 = close.rolling(50).mean()
            ema21_close = close.ewm(span=21, adjust=False).mean()
            ema21_low   = low.ewm(span=21, adjust=False).mean()

            tr = pd.concat([
                high - low,
                (high - close.shift(1)).abs(),
                (low - close.shift(1)).abs()
            ], axis=1).max(axis=1)
            atr = tr.rolling(14).mean()
            atrPercent = (atr / close) * 100

            atr21_R = (((close - ema21_close) / close) * 100) / (atrPercent + 1e-6)
            atr50_R = (((close - sma50) / close) * 100) / (atrPercent + 1e-6)
            emaDistPercent = ((close - ema21_low) / close) * 100

            hl_ratio = high / low
            adrPercent = 100 * (hl_ratio.rolling(20).mean() - 1)

            cond1 = (adrPercent.iloc[-1] >= 2.45) and (adrPercent.iloc[-1] < 8.05)
            cond2 = -0.5 <= atr21_R.iloc[-1] <= 1
            cond3 = 0 <= atr50_R.iloc[-1] <= 3
            cond4 = 0 < emaDistPercent.iloc[-1] <= 8

            if cond1 and cond2 and cond3 and cond4:
                filtered.append(ticker)

        except Exception:
            continue

    return sorted(filtered), sorted(unfiltered)

@st.cache_data(ttl=3600)
def compute_early_bull_history(stocks_list, ticker_dfs, benchmark_df_input):
    """
    Vectorized version of the Stage 1->2 / Stage 4->2 transition logic from
    compute_early_bull, evaluated across the FULL time series (not just the
    latest bar) so we get a daily Early Bull count history, mirroring how
    compute_two_botak_history / compute_stage_history work.
    Note: unlike compute_early_bull, this does NOT apply the cond1-cond4
    (ADR%/ATR%/EMA-distance) filters — it only tracks the stage transition condition.
    """
    try:
        if benchmark_df_input is None or benchmark_df_input.empty:
            return pd.DataFrame()

        bm_idx = benchmark_df_input.index.tz_localize(None) if benchmark_df_input.index.tz is not None else benchmark_df_input.index
        bm_aligned = benchmark_df_input.copy()
        bm_aligned.index = bm_idx

        all_series = []

        for ticker in stocks_list:
            try:
                df = ticker_dfs.get(ticker)
                if df is None or len(df) < 260:
                    continue

                df_idx = df.index.tz_localize(None) if df.index.tz is not None else df.index
                df_aligned = df.copy()
                df_aligned.index = df_idx

                combined = pd.merge(
                    df_aligned[['Close', 'Open', 'High', 'Low']],
                    bm_aligned[['Close']].rename(columns={'Close': 'Close_bench'}),
                    left_index=True, right_index=True, how='inner'
                )
                if len(combined) < 260:
                    continue

                close = combined['Close']
                high  = combined['High']

                ema126 = df_aligned['Close'].ewm(span=126, adjust=False).mean().reindex(combined.index, method='ffill')
                rs = close / combined['Close_bench']

                ema_spans = [21, 42, 63, 72, 84, 126, 147, 168]
                r = {s: rs.ewm(span=s, adjust=False).mean() for s in ema_spans}

                stage1_cond = (rs >= r[84]) & (rs < r[126])
                stage3_cond = (
                    (rs < r[42]) & (rs >= r[72]) & (rs >= r[84]) & (rs >= r[126])
                    & ((r[42] > r[63]) | (rs < r[63])) & (r[63] > r[126]) & (close >= ema126)
                )
                stage2a_cond = (
                    (rs >= r[168]) & (rs >= r[147]) & (rs >= r[126])
                    & (close >= ema126) & ((r[21] >= r[42]) | (r[42] >= r[63]))
                )
                stage2b_cond = (rs >= r[126]) & (close >= ema126) & ((r[21] >= r[42]) | (r[42] >= r[63]))
                stage4_cond = ((rs < r[63]) & (rs < r[126])) | ((r[63] < r[126]) & (rs < r[126]))

                stage_num = pd.Series(0, index=combined.index)
                stage_num[stage1_cond] = 1
                remaining = ~stage1_cond
                stage_num[remaining & stage3_cond] = 3
                remaining = remaining & ~stage3_cond
                stage_num[remaining & (stage2a_cond | stage2b_cond)] = 2
                remaining = remaining & ~(stage2a_cond | stage2b_cond)
                stage_num[remaining & stage4_cond] = 4

                stage_prev = stage_num.shift(1)
                stage1to2Transition = (stage_num == 2) & ((stage_prev == 1) | (stage_prev == 4))

                transition_price = high.where(stage1to2Transition)
                stage1to2Price = transition_price.ffill()

                stage1to2Count30 = stage1to2Transition.astype(int).rolling(30).sum()
                stage1to2Recent30 = stage1to2Count30 >= 1
                stage1to2PriceAbove = stage1to2Price.notna() & (close > stage1to2Price)

                stage1to2AlertCond = stage1to2Recent30 & stage1to2PriceAbove & (stage_num == 2) & (close >= 20)

                all_series.append(stage1to2AlertCond.astype(int))
            except Exception:
                continue

        if not all_series:
            return pd.DataFrame()

        combined_all = pd.concat(all_series, axis=1).fillna(0)
        daily_counts = combined_all.sum(axis=1)

        result = daily_counts.tail(60).reset_index()
        result.columns = ["Date", "Early Bull Count"]
        result["Date"] = result["Date"].dt.strftime("%Y-%m-%d")
        return result
    except Exception:
        return pd.DataFrame()


st.markdown("---")

# with st.spinner("Scanning Early Bull setups..."):
#     early_bull_list = timed(
#         "compute_early_bull",
#         compute_early_bull,
#         stocks_tuple, ticker_dfs_shared, benchmark_df_shared
#     )

# st.markdown(f"#### 🐂 Early Bull = buyable Sector ({len(early_bull_list)})")

# if early_bull_list:
#     # Map each Early Bull ticker to its industry group(s), reusing the same
#     # helper used for the RS Leader section.
#     eb_industry_counts, eb_ticker_industry = build_leader_industry_map(early_bull_list, INDUSTRIES)

#     html_eb = ""
#     for sym in early_bull_list:
#         industries = eb_ticker_industry.get(sym, [])
#         ranks = [industry_rank_map[ind] for ind in industries if ind in industry_rank_map]
#         is_top20_industry = any(r <= 20 for r in ranks) if ranks else False

#         glow_style = (
#             "box-shadow:0 0 8px 2px #FFA500; border:1px solid #FFA500;"
#             if is_top20_industry else ""
#         )

#         html_eb += setup_badge(sym, extra_style=glow_style)

#     st.markdown(html_eb, unsafe_allow_html=True)
# else:
#     st.info("No active setups discovered.")

# st.write("")

# with st.spinner("Scanning Early Bull (unfiltered) setups..."):
#     early_bull_no_filter_list = timed(
#         "compute_early_bull_no_filter",
#         compute_early_bull_no_filter,
#         stocks_tuple, ticker_dfs_shared, benchmark_df_shared
#     )

with st.spinner("Scanning Early Bull setups..."):
    early_bull_list, early_bull_no_filter_list = timed(
        "compute_early_bull_combined",
        compute_early_bull_combined,
        stocks_tuple, ticker_dfs_shared, benchmark_df_shared
    )

st.markdown(f"#### 🐂 Early Bull = buyable + Sector + ALL ({len(early_bull_list)} + ... + {len(early_bull_no_filter_list)})")

if early_bull_no_filter_list:
    eb_nf_industry_counts, eb_nf_ticker_industry = build_leader_industry_map(early_bull_no_filter_list, INDUSTRIES)
    early_bull_set = set(early_bull_list)   # NEW — for O(1) membership check

    html_eb_nf = ""
    for sym in early_bull_no_filter_list:
        industries = eb_nf_ticker_industry.get(sym, [])
        ranks = [industry_rank_map[ind] for ind in industries if ind in industry_rank_map]
        is_top20_industry = any(r <= 20 for r in ranks) if ranks else False

        glow_style = (
            "box-shadow:0 0 8px 2px #FF4B4B; border:1px solid #FF4B4B;"
            if is_top20_industry else ""
        )
        badge_style = "background:#C71585;" if sym in early_bull_set else ""

        html_eb_nf += setup_badge(sym, extra_style=glow_style + badge_style)

    st.markdown(html_eb_nf, unsafe_allow_html=True)

    render_group_ai_insight(
        early_bull_no_filter_list,
        "Early Bull (unfiltered stage transition)",
        "early_bull_no_filter",
        extra_note="stock just transitioned from Stage 1 or Stage 4 into Stage 2 within the last 30 bars and price is holding above the transition-bar high, WITHOUT the ADR%/ATR%/EMA-distance quality filters applied"
    )
else:
    st.info("No active setups discovered.")

st.write("")

with st.spinner("Scanning for Early Bull History..."):
    early_bull_hist = timed(
        "compute_early_bull_history",
        compute_early_bull_history,
        stocks_tuple, ticker_dfs_shared, benchmark_df_shared
    )

if not early_bull_hist.empty:
    chart_df_eb = early_bull_hist.copy()
    today_value_eb = chart_df_eb["Early Bull Count"].iloc[-1]
    max_value_eb = chart_df_eb["Early Bull Count"].max()

    chart_df_eb["Bar_Color"] = "#29B5E8"

    # NEW: statistical outliers (>=2 std dev above mean) turn red
    mean_eb = chart_df_eb["Early Bull Count"].mean()
    std_eb  = chart_df_eb["Early Bull Count"].std(ddof=1)
    if std_eb and std_eb > 0:
        z_scores_eb = (chart_df_eb["Early Bull Count"] - mean_eb) / std_eb
    else:
        z_scores_eb = pd.Series(0, index=chart_df_eb.index)
    chart_df_eb.loc[z_scores_eb >= 2, "Bar_Color"] = "#FF4B4B"

    if today_value_eb == max_value_eb:
        chart_df_eb.iloc[-1, chart_df_eb.columns.get_loc("Bar_Color")] = "#FF4B4B"

    st.bar_chart(
        data=chart_df_eb,
        x="Date",
        y="Early Bull Count",
        color="Bar_Color",
        use_container_width=True
    )

st.markdown("---")
#st.write(f"inside check: {len(ticker_dfs_shared)}")

with st.spinner("Scanning for Two Botak History..."):
    two_botak_hist= timed("compute_two_botak_history",     compute_two_botak_history,     stocks_tuple, ticker_dfs_shared)

#st.write(f"two_botak_hist shape: {two_botak_hist.shape}")

# --- 1. TWO BOTAK (Full Horizontal Row) ---
two_botak_count_color = "#FF6B6B" if len(b_list) == 0 else "inherit"
st.markdown(
    f"<h4>🧑‍🦲 Two Botak = Short term Group burst <span style='color:{two_botak_count_color}; font-weight:bold;'>({len(b_list)})</span></h4>",
    unsafe_allow_html=True
)
if b_list or b_yest:
    html_b = ""
    b_industry_counts, b_ticker_industry = build_leader_industry_map(b_list, INDUSTRIES)  # NEW
    for sym in b_list:
        # NEW: top-20 industry glow
        industries = b_ticker_industry.get(sym, [])
        ranks = [industry_rank_map[ind] for ind in industries if ind in industry_rank_map]
        is_top20_industry = any(r <= 20 for r in ranks) if ranks else False
        glow_style = (
            "box-shadow:0 0 8px 2px #FF4B4B; border:1px solid #FF4B4B;"
            if is_top20_industry else ""
        )
        html_b += setup_badge(sym, is_new=(sym not in b_yest), extra_style=glow_style)  # CHANGED
    
    removed_b = [sym for sym in b_yest if sym not in b_list]
    for sym in sorted(removed_b):
        html_b += f'<div class="ticker-badge removed-badge">{sym}</div>'
        
    st.markdown(html_b, unsafe_allow_html=True)

    render_group_ai_insight(
        b_list,
        "Two Botak (short-term group burst)",
        "two_botak",
        extra_note="2 consecutive daily bullish candles where the close is at or almost at the high of the day"
    )
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

    # 3. Compute z-scores vs the window's mean/std
    mean_val = chart_df["Two Botak Count"].mean()
    std_val  = chart_df["Two Botak Count"].std(ddof=1)

    if std_val and std_val > 0:
        z_scores = (chart_df["Two Botak Count"] - mean_val) / std_val
    else:
        z_scores = pd.Series(0, index=chart_df.index)

    # 4. Default: every bar blue
    chart_df["Bar_Color"] = "#29B5E8"

    # Statistical outliers (>=2 std dev above mean) turn red
    chart_df.loc[z_scores >= 2, "Bar_Color"] = "#FF4B4B"

    # Latest bar also turns red if it's the highest in the window (ties count)
    if today_value == max_value:
        chart_df.iloc[-1, chart_df.columns.get_loc("Bar_Color")] = "#FF4B4B"

    # 5. Render chart mapping color directly to the new dataframe column
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
engulf_count_color = "#FF6B6B" if total_engulf == 0 else "inherit"
st.markdown(
    f"<h4>🐳 Engulfing = HL <span style='color:{engulf_count_color}; font-weight:bold;'>({total_engulf})</span></h4>",
    unsafe_allow_html=True
)

if e2_list or e2_yest:
    st.markdown(f"**2x Engulfing ({len(e2_list)}):**")
    html_e2 = ""
    e2_industry_counts, e2_ticker_industry = build_leader_industry_map(e2_list, INDUSTRIES)  # NEW
    for sym in e2_list:
        # NEW: top-20 industry glow
        industries = e2_ticker_industry.get(sym, [])
        ranks = [industry_rank_map[ind] for ind in industries if ind in industry_rank_map]
        is_top20_industry = any(r <= 20 for r in ranks) if ranks else False
        glow_style = (
            "box-shadow:0 0 8px 2px #FF4B4B; border:1px solid #FF4B4B;"
            if is_top20_industry else ""
        )
        html_e2 += setup_badge(sym, is_new=(sym not in e2_yest), extra_style=glow_style)  # CHANGED
    
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

#st.write("")
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

    st.bar_chart(
        data=chart_df_2x,
        x="Date",
        y="2x Engulfing Count",
        color="Bar_Color",
        use_container_width=True
    )

if e3_list or e3_yest:
    if len(e3_list) == 0 and len(e3_yest) == 0:
        st.markdown("**3x Engulfing (0):**")
    elif e3_list or e3_yest:
        st.markdown(f"<div style='margin-top:10px;'><b>3x Engulfing ({len(e3_list)}):</b></div>", unsafe_allow_html=True)
        html_e3 = ""
        e3_industry_counts, e3_ticker_industry = build_leader_industry_map(e3_list, INDUSTRIES)  # NEW
        for sym in e3_list:
            # NEW: top-20 industry glow
            industries = e3_ticker_industry.get(sym, [])
            ranks = [industry_rank_map[ind] for ind in industries if ind in industry_rank_map]
            is_top20_industry = any(r <= 20 for r in ranks) if ranks else False
            glow_style = (
                "box-shadow:0 0 8px 2px #FF4B4B; border:1px solid #FF4B4B;"
                if is_top20_industry else ""
            )
            html_e3 += setup_badge(sym, is_new=(sym not in e3_yest), extra_style=glow_style)  # CHANGED
            
        removed_e3 = [sym for sym in e3_yest if sym not in e3_list]
        for sym in sorted(removed_e3):
            html_e3 += f'<div class="ticker-badge removed-badge">{sym}</div>'
            
        st.markdown(html_e3, unsafe_allow_html=True)
else:
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

    st.bar_chart(
        data=chart_df_3x,
        x="Date",
        y="3x Engulfing Count",
        color="Bar_Color",
        use_container_width=True
    )

engulf_combined_syms = list(dict.fromkeys(e2_list + e3_list))
render_group_ai_insight(
    engulf_combined_syms,
    "Bullish Engulfing (2x/3x)",
    "engulfing",
    extra_note="2 or 3 recent bullish engulfing candles (open below prior low, close above prior high) with price closing above the prior engulfing candle closes"
)

# --- EXTRA TREND METRICS (Stacked Horizontally Below Patterns) ---
#st.markdown("---")
#st.markdown("### 📊 Extra Trend Metrics (PowerTrend Indicators)")
#st.markdown("<br>", unsafe_allow_html=True) # Spacer

st.markdown("---")

with st.spinner("Scanning for PowerTrend History..."):
    powertrend_hist=timed("compute_powertrend_history",    compute_powertrend_history,    stocks_tuple, ticker_dfs_shared)

# --- 4. POWERTREND (Full Horizontal Row) ---
powertrend_count_color = "#FF6B6B" if len(pt_list) == 0 else "inherit"
st.markdown(
    f"<h4>⚡ PowerTrend = Thematic Extended <span style='color:{powertrend_count_color}; font-weight:bold;'>({len(pt_list)})</span></h4>",
    unsafe_allow_html=True
)
if pt_list or pt_yest:
    html_pt = ""
    pt_yest_set = set(pt_yest)
    current_pt_tickers = {item[0] if isinstance(item, tuple) else item for item in pt_list}
    pt_industry_counts, pt_ticker_industry = build_leader_industry_map(sorted(current_pt_tickers), INDUSTRIES)  # NEW
    for item in pt_list:
        sym = item[0] if isinstance(item, tuple) else item
        atr_value = item[1] if isinstance(item, tuple) else None
        suffix = f"{atr_value:.1f}x" if atr_value is not None else ""
        suffix_color = "#00FF00" if (atr_value is not None and atr_value < 4) else "#888888"
        # NEW: top-20 industry glow
        industries = pt_ticker_industry.get(sym, [])
        ranks = [industry_rank_map[ind] for ind in industries if ind in industry_rank_map]
        is_top20_industry = any(r <= 20 for r in ranks) if ranks else False
        glow_style = (
            "box-shadow:0 0 8px 2px #FF4B4B; border:1px solid #FF4B4B;"
            if is_top20_industry else ""
        )
        html_pt += setup_badge(sym, is_new=(sym not in pt_yest_set), extra_suffix=suffix, extra_suffix_color=suffix_color, extra_style=glow_style)  # CHANGED
    
    removed_pt = [sym for sym in pt_yest if sym not in current_pt_tickers]
    for sym in sorted(removed_pt):
        html_pt += f'<div class="ticker-badge removed-badge">{sym}</div>'
        
    st.markdown(html_pt, unsafe_allow_html=True)

    pt_syms = [item[0] if isinstance(item, tuple) else item for item in pt_list]
    render_group_ai_insight(
        pt_syms,
        "PowerTrend (thematic extended)",
        "powertrend",
        extra_note="absolute gradient % of the 50-day EMA is greater than 1, indicating a fast-rising moving average"
    )
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

    # NEW: statistical outliers (>=2 std dev above mean) turn red
    mean_val = chart_df["PowerTrend Count"].mean()
    std_val  = chart_df["PowerTrend Count"].std(ddof=1)
    if std_val and std_val > 0:
        z_scores = (chart_df["PowerTrend Count"] - mean_val) / std_val
    else:
        z_scores = pd.Series(0, index=chart_df.index)
    chart_df["Bar_Color"] = "#29B5E8"
    chart_df.loc[z_scores >= 2, "Bar_Color"] = "#FF4B4B"
    
    # 3. Add an explicit 'Bar_Color' column to your dataframe
    if today_value == max_value or today_value == min_value:
        # Define base color, then override the last row (today) with your accent color
        chart_df.iloc[-1, chart_df.columns.get_loc("Bar_Color")] = "#FF4B4B"
    # else: leave as-is (already blue, or red from z-score outlier check above)

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
# st.markdown(f"#### ⚡ PowerTrend ... Not Extended ({len(ptne_list)})")
# if ptne_list:
#     html_ptne = ""
#     ptne_yest_set = set(ptne_yest)
#     for item in ptne_list:
#         sym = item[0] if isinstance(item, tuple) else item
#         atr_value = item[1] if isinstance(item, tuple) else None
#         suffix = f"{atr_value:.1f}x" if atr_value is not None else ""
#         html_ptne += setup_badge(sym, is_new=(sym not in ptne_yest_set), extra_suffix=suffix)
#     st.markdown(html_ptne, unsafe_allow_html=True)
# else:
#     st.info("No active setups discovered.")

# ============================================================
# VOLATILITY PICKUP — Z-Score of Daily Range >= 2
# ============================================================
@st.cache_data(ttl=3600)
def compute_volatility_pickup(stocks_list, _ticker_dfs):
    """
    For each ticker, compute:
        dailyRange = 100 * (high / low - 1)
        avgRange   = SMA(dailyRange, 20)
        stdRange   = STDEV(dailyRange, 20)
        z          = (dailyRange - avgRange) / stdRange
    Return list of (ticker, z_score) where z >= 2, sorted descending by z.
    """
    results = []
    for ticker in stocks_list:
        try:
            df = _ticker_dfs.get(ticker)
            if df is None or len(df) < 22:
                continue
            high  = df['High']
            low   = df['Low']
            close = df['Close']

            if close.iloc[-1] < 20:
                continue

            daily_range = 100 * (high / low - 1)
            avg_range   = daily_range.rolling(20).mean()
            std_range   = daily_range.rolling(20).std(ddof=1)

            z_series = (daily_range - avg_range) / std_range.replace(0, float('nan'))

            z_today = z_series.iloc[-1]
            if pd.isna(z_today) or z_today < 2:
                continue

            close = df['Close']
            pct_chg = (close.iloc[-1] - close.iloc[-2]) / close.iloc[-2] * 100 if len(close) >= 2 and close.iloc[-2] != 0 else 0.0
            results.append((ticker, round(float(z_today), 2), round(float(pct_chg), 2)))
        except Exception:
            continue

    results.sort(key=lambda x: x[0])
    return results


with st.spinner("Scanning volatility pickup..."):
    volatility_hits = timed(
        "compute_volatility_pickup",
        compute_volatility_pickup,
        stocks_tuple, ticker_dfs_shared
    )

#st.markdown("---")
volatility_count_color = "#FF6B6B" if len(volatility_hits) == 0 else "inherit"
volatility_up_count = sum(1 for sym, z, pct in volatility_hits if pct >= 0)
volatility_down_count = len(volatility_hits) - volatility_up_count
st.markdown(
    f"<h4>〽️ Volatility = TV Horizontal Line <span style='color:{volatility_count_color}; font-weight:bold;'>"
    f"({len(volatility_hits)} = {volatility_up_count} + {volatility_down_count})</span></h4>",
    unsafe_allow_html=True
)

if volatility_hits:
    vol_html = "<div style='display:flex; flex-wrap:wrap; gap:4px; padding:6px 0;'>"
    for sym, z, pct in volatility_hits:
        if pct >= 0:
            bg       = "#90EE90"   # light green
            border   = "#228B22"
            txt_col  = "#003300"   # dark green — readable on light green
            z_col    = "#005500"
        else:
            bg       = "#FFB3B3"   # light red
            border   = "#CC0000"
            txt_col  = "#4B0000"   # dark red — readable on light red
            z_col    = "#6B0000"
        pct_sign = f"+{pct:.1f}%" if pct >= 0 else f"{pct:.1f}%"
        vol_html += (
            f'<div class="ticker-badge volatility-badge" style="background:{bg}; border:1px solid {border};">'
            f'<span class="ticker-name" style="color:{txt_col};">{sym}</span>'
            f'<span class="ticker-rs" style="color:{z_col}; margin-left:4px;"> {z:.1f}z</span>'
            f'<span class="ticker-rs" style="color:{txt_col}; margin-left:4px;"> {pct_sign}</span>'
            f'</div>'
        )
    vol_html += "</div>"
    st.markdown(vol_html, unsafe_allow_html=True)

    vol_syms = [sym for sym, z, pct in volatility_hits]
    render_group_ai_insight(
        vol_syms,
        "Volatility pickup (Z-score ≥2)",
        "volatility",
        extra_note="daily range Z-score (vs its 20-day mean/stdev) is at or above 2, flagging an unusually large range day"
    )
else:
    st.info("No tickers with volatility Z-score ≥ 2 today.")

with st.spinner("Scanning for Volatility History..."):
    volatility_hist = timed("compute_volatility_history", compute_volatility_history, stocks_tuple, ticker_dfs_shared)

st.write("")
if not volatility_hist.empty:
    chart_df_v = volatility_hist.copy()

    today_v = chart_df_v["Volatility Count"].iloc[-1]
    max_v   = chart_df_v["Volatility Count"].max()

    mean_v = chart_df_v["Volatility Count"].mean()
    std_v  = chart_df_v["Volatility Count"].std(ddof=1)

    if std_v and std_v > 0:
        z_scores = (chart_df_v["Volatility Count"] - mean_v) / std_v
    else:
        z_scores = pd.Series(0, index=chart_df_v.index)

    # Default: every bar blue
    chart_df_v["Bar_Color"] = "#29B5E8"

    # Statistical outliers (>=2 std dev above mean) turn red
    chart_df_v.loc[z_scores >= 2, "Bar_Color"] = "#FF4B4B"

    # Latest bar also turns red if it's the highest in the window (ties count)
    if today_v == max_v:
        chart_df_v.iloc[-1, chart_df_v.columns.get_loc("Bar_Color")] = "#FF4B4B"

    st.bar_chart(
        data=chart_df_v,
        x="Date",
        y="Volatility Count",
        color="Bar_Color",
        use_container_width=True
    )

#st.markdown("<br>", unsafe_allow_html=True) # Spacer
st.markdown("---")

@st.cache_data(ttl=86400)
def fetch_wide_moat_tickers(tickers_tuple):
    """
    Approximate 'wide moat' flag using FMP fundamental data.
    FMP has no direct moat field, so this proxies durable competitive
    advantage via sustained high returns on capital:
      - Avg ROE >= 15% and Avg ROIC >= 12% over available annual years
      - No more than 1 negative-ROE year, with at least 3 years of data
    On ANY failure (missing key, bad response, ticker not covered,
    malformed data) that ticker is silently skipped — never flagged,
    never raises. Returns a set of tickers considered wide-moat.
    """
    fmp_key = st.secrets.get("FMP_API_KEY")
    moat_set = set()

    if not fmp_key or not tickers_tuple:
        return moat_set

    for ticker in tickers_tuple:
        try:
            resp = requests.get(
                f"https://financialmodelingprep.com/api/v3/key-metrics/{ticker}",
                params={"period": "annual", "limit": 10, "apikey": fmp_key},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()

            if not data or not isinstance(data, list):
                continue

            roe_vals = [
                d.get("roe") for d in data
                if isinstance(d, dict) and isinstance(d.get("roe"), (int, float))
            ]
            roic_vals = [
                d.get("roic") for d in data
                if isinstance(d, dict) and isinstance(d.get("roic"), (int, float))
            ]

            if len(roe_vals) < 3:
                continue

            avg_roe = sum(roe_vals) / len(roe_vals)
            avg_roic = (sum(roic_vals) / len(roic_vals)) if roic_vals else 0
            negative_years = sum(1 for r in roe_vals if r < 0)

            if avg_roe >= 0.15 and avg_roic >= 0.12 and negative_years <= 1:
                moat_set.add(ticker)

        except Exception:
            # Fallback: treat as not-wide-moat, never error out
            continue

    return moat_set

# --- 6. VALUE TRAP (Full Horizontal Row Below PowerTrend Not Extended) ---
value_trap_count_color = "#00FF00" if len(vt_list) == 0 else "inherit"
st.markdown(
    f"<h4>⚠️ Value Trap = MAG7 & MOAT <span style='color:{value_trap_count_color}; font-weight:bold;'>({len(vt_list)})</span></h4>",
    unsafe_allow_html=True
)

if vt_list or vt_yest:
    html_vt = ""
    vt_yest_set = set(vt_yest)
    current_vt_tickers = {item[0] if isinstance(item, tuple) else item for item in vt_list}

    # NEW: check wide-moat status for today's Value Trap tickers only
    vt_syms_for_moat = tuple(sorted(current_vt_tickers))
    with st.spinner("Checking wide-moat status..."):
        wide_moat_tickers = timed(
            "fetch_wide_moat_tickers",
            fetch_wide_moat_tickers,
            vt_syms_for_moat
        )

    for item in vt_list:
        sym = item[0] if isinstance(item, tuple) else item
        atr_value = item[1] if isinstance(item, tuple) else None
        suffix = f"{atr_value:.1f}x" if atr_value is not None else ""
        moat_glow = (
            "box-shadow:0 0 8px 2px #FF0000; border:1px solid #FF0000;"
            if sym in wide_moat_tickers else ""
        )
        html_vt += setup_badge(sym, is_new=(sym not in vt_yest_set), extra_suffix=suffix, extra_style=moat_glow)
    
    # Process and append removed stocks
    removed_vt = [sym for sym in vt_yest if sym not in current_vt_tickers]
    for sym in sorted(removed_vt):
        html_vt += f'<div class="ticker-badge removed-badge">{sym}</div>'
        
    st.markdown(html_vt, unsafe_allow_html=True)

    vt_syms = [item[0] if isinstance(item, tuple) else item for item in vt_list]
    render_group_ai_insight(
        vt_syms,
        "Value Trap",
        "value_trap",
        extra_note="price is roughly -4x ATR below its 50-day moving average, suggesting deep extension to the downside rather than genuine value"
    )
else:
    st.info("No active setups discovered.")

with st.spinner("Scanning for Value Trap History..."):
    value_trap_hist = timed("compute_value_trap_history", compute_value_trap_history, stocks_tuple, ticker_dfs_shared)

st.write("")
if not value_trap_hist.empty:
    chart_df_vt = value_trap_hist.copy()

    today_vt = chart_df_vt["Value Trap Count"].iloc[-1]
    max_vt   = chart_df_vt["Value Trap Count"].max()

    # Default: every bar blue
    chart_df_vt["Bar_Color"] = "#29B5E8"

    # NEW: statistical outliers (>=2 std dev above mean) turn red
    mean_vt = chart_df_vt["Value Trap Count"].mean()
    std_vt  = chart_df_vt["Value Trap Count"].std(ddof=1)
    if std_vt and std_vt > 0:
        z_scores_vt = (chart_df_vt["Value Trap Count"] - mean_vt) / std_vt
    else:
        z_scores_vt = pd.Series(0, index=chart_df_vt.index)
    chart_df_vt.loc[z_scores_vt >= 2, "Bar_Color"] = "#FF4B4B"

    # Only the LATEST bar turns red, and only if it's also the highest
    # value across the whole 60-day window (ties count as "highest" too)
    if today_vt == max_vt:
        chart_df_vt.iloc[-1, chart_df_vt.columns.get_loc("Bar_Color")] = "#FF4B4B"

    st.bar_chart(
        data=chart_df_vt,
        x="Date",
        y="Value Trap Count",
        color="Bar_Color",
        use_container_width=True
    )

# ============================================================
# CHANGE OF CHARACTER (scoreUp20) — Composite Score Δ≥20 Scan
# Ported from TradingView "Score" indicator's scoreUp20 signal.
# score5 (Darvas streak) omitted; score6/score7 use lite proxies
# — see docstring below for full mapping.
# ============================================================
@st.cache_data(ttl=3600)
def compute_character_shift(stocks_list, ticker_dfs, benchmark_df_input):
    """
    Single-pass version of compute_change_of_character that returns BOTH
    directions of the composite score's day-over-day delta:
      - Change of Character   : score jumped by >= 20 (bullish)
      - Breakdown of Character: score dropped by >= 20 (bearish)
    Same 9-component score (score5/Darvas-streak omitted; score6/score7
    use lite proxies) as compute_change_of_character — see that function's
    docstring for the full component mapping.
    """
    up_today, up_yest     = [], []
    down_today, down_yest = [], []
    up_score_map, up_delta_map     = {}, {}
    down_score_map, down_delta_map = {}, {}
    all_up20_series, all_down20_series = [], []

    for ticker in stocks_list:
        try:
            df = ticker_dfs.get(ticker)
            if df is None or len(df) < 260:
                continue

            close = df['Close']; high = df['High']; low = df['Low']

            rs = close / benchmark_df_input['Close']
            if rs.dropna().empty:
                continue

            ema126 = close.ewm(span=126, adjust=False).mean()
            r = {sp: rs.ewm(span=sp, adjust=False).mean() for sp in [21, 42, 63, 72, 84, 126, 147, 168]}

            stage1_cond  = (rs >= r[84]) & (rs < r[126])
            stage3_cond  = (
                (rs < r[42]) & (rs >= r[72]) & (rs >= r[84]) & (rs >= r[126])
                & ((r[42] > r[63]) | (rs < r[63])) & (r[63] > r[126]) & (close >= ema126)
            )
            stage2a_cond = (
                (rs >= r[168]) & (rs >= r[147]) & (rs >= r[126])
                & (close >= ema126) & ((r[21] >= r[42]) | (r[42] >= r[63]))
            )
            stage2b_cond = (rs >= r[126]) & (close >= ema126) & ((r[21] >= r[42]) | (r[42] >= r[63]))
            stage2_cond  = (~stage1_cond & ~stage3_cond & (stage2a_cond | stage2b_cond))

            rsMA21  = rs.ewm(span=21, adjust=False).mean()
            ema21   = close.ewm(span=21, adjust=False).mean()
            sma50   = close.rolling(50).mean()
            low14   = low.rolling(14).min().shift(1)
            ema50t  = close.ewm(span=50, adjust=False).mean()
            ema100t = close.ewm(span=100, adjust=False).mean()

            gap_down_evt       = (high < low.shift(1))
            gap_down_pct       = ((close.shift(1) - close) / close.shift(1) * 100).where(gap_down_evt)
            gap_down_qualified = gap_down_evt & (gap_down_pct >= 3)
            recent_gap_down    = gap_down_qualified.rolling(10, min_periods=1).max().fillna(0).astype(bool)

            pct_chg = close.pct_change() * 100
            win = min(220, len(pct_chg))
            biggest_drop = pct_chg.rolling(window=win, min_periods=20).min()
            biggest_up   = pct_chg.rolling(window=win, min_periods=20).max()

            high252 = high.rolling(252, min_periods=50).max()
            pct_from_high = (close - high252) / high252 * 100

            s1  = (rs > rsMA21).fillna(False).astype(int) * 10
            s2  = stage2_cond.fillna(False).astype(int) * 10
            s3  = (close > ema21).fillna(False).astype(int) * 10
            s4  = (close > sma50).fillna(False).astype(int) * 10
            s6  = (~(close < low14).fillna(False)).astype(int) * 10
            s7  = (~recent_gap_down).astype(int) * 10
            s8  = (~(biggest_up < -biggest_drop).fillna(False)).astype(int) * 10
            s9  = (~(pct_from_high < -25).fillna(False)).astype(int) * 10
            s10 = (ema50t >= ema100t).fillna(False).astype(int) * 10

            score = s1 + s2 + s3 + s4 + s6 + s7 + s8 + s9 + s10
            score_delta = score.diff()
            score_up20   = (score_delta >= 20)
            score_down20 = (score_delta <= -20)

            all_up20_series.append(score_up20.astype(int).rename(ticker))
            all_down20_series.append(score_down20.astype(int).rename(ticker))

            current_close = float(close.iloc[-1]) if pd.notna(close.iloc[-1]) else np.nan
            is_price_above_20 = pd.notna(current_close) and current_close > 20

            if len(score) >= 2:
                if is_price_above_20 and bool(score_up20.iloc[-1]):
                    up_today.append(ticker)
                    up_score_map[ticker] = int(score.iloc[-1])
                    up_delta_map[ticker] = int(score.iloc[-1] - score.iloc[-2])
                if is_price_above_20 and bool(score_down20.iloc[-1]):
                    down_today.append(ticker)
                    down_score_map[ticker] = int(score.iloc[-1])
                    down_delta_map[ticker] = int(score.iloc[-1] - score.iloc[-2])
                if len(score_up20) >= 3:
                    if is_price_above_20 and bool(score_up20.iloc[-2]):
                        up_yest.append(ticker)
                    if is_price_above_20 and bool(score_down20.iloc[-2]):
                        down_yest.append(ticker)
        except Exception:
            continue

    def _hist(series_list, col_name):
        if not series_list:
            return pd.DataFrame()
        combined = pd.concat(series_list, axis=1).fillna(0)
        daily_counts = combined.sum(axis=1)
        out = daily_counts.tail(60).reset_index()
        out.columns = ["Date", col_name]
        out["Date"] = pd.to_datetime(out["Date"]).dt.strftime("%Y-%m-%d")
        return out

    up_hist   = _hist(all_up20_series, "CoC Count")
    down_hist = _hist(all_down20_series, "BoC Count")

    return (
        sorted(up_today), sorted(up_yest), up_score_map, up_delta_map, up_hist,
        sorted(down_today), sorted(down_yest), down_score_map, down_delta_map, down_hist,
    )

# ── Render section — append at the very bottom of the dashboard ────────────
st.markdown("---")

with st.spinner("Scanning for Change / Breakdown of Character (Score Δ≥20)..."):
    (coc_today, coc_yest, coc_score_map, coc_delta_map, coc_hist,
     boc_today, boc_yest, boc_score_map, boc_delta_map, boc_hist) = timed(
        "compute_character_shift",
        compute_character_shift,
        stocks_tuple, ticker_dfs_shared, benchmark_df_shared
    )

# ═══════════════════ CHANGE OF CHARACTER (Δ ≥ +20) ═══════════════════
st.markdown(
    f"#### 🔀 Change of Character ({len(coc_today)}) "
    f"<span style='color:#888; font-size:12px;'>[Grey out = 2x CoC]</span>",
    unsafe_allow_html=True,
)

if coc_today or coc_yest:
    coc_industry_counts, coc_ticker_industry = build_leader_industry_map(coc_today, INDUSTRIES)

    html_coc = ""
    for sym in coc_today:  # alphabetical
        industries = coc_ticker_industry.get(sym, [])
        ranks = [industry_rank_map[ind] for ind in industries if ind in industry_rank_map]
        is_top20_industry = any(r <= 20 for r in ranks) if ranks else False
        glow_style = (
            "box-shadow:0 0 8px 2px #FF4B4B; border:1px solid #FF4B4B;"
            if is_top20_industry else ""
        )
        delta = coc_delta_map.get(sym, 0)
        score_val = coc_score_map.get(sym, 0)
        suffix = f"{score_val} (+{delta})"
        html_coc += setup_badge(
            sym,
            is_new=(sym not in coc_yest),
            extra_style=glow_style,
            extra_suffix=suffix,
            extra_suffix_color="#006400",  # dark green
        )

    removed_coc = [sym for sym in coc_yest if sym not in coc_today]
    for sym in sorted(removed_coc):
        html_coc += f'<div class="ticker-badge removed-badge">{sym}</div>'

    st.markdown(html_coc, unsafe_allow_html=True)

    render_group_ai_insight(
        coc_today,
        "Change of Character (Score jump ≥20)",
        "change_of_character",
        extra_note="the stock's composite health score (RS-vs-benchmark, stage, trend, gap, and drawdown-symmetry checks) jumped by 20+ points day-over-day, signaling a fast-improving technical picture / bullish character change"
    )
else:
    st.info("No active setups discovered.")

st.write("")
if not coc_hist.empty:
    chart_df_coc = coc_hist.copy()

    today_coc = chart_df_coc["CoC Count"].iloc[-1]
    max_coc   = chart_df_coc["CoC Count"].max()

    mean_coc = chart_df_coc["CoC Count"].mean()
    std_coc  = chart_df_coc["CoC Count"].std(ddof=1)

    if std_coc and std_coc > 0:
        z_scores_coc = (chart_df_coc["CoC Count"] - mean_coc) / std_coc
    else:
        z_scores_coc = pd.Series(0, index=chart_df_coc.index)

    # Default: every bar blue
    chart_df_coc["Bar_Color"] = "#29B5E8"

    # Statistical outliers (>=2 std dev above mean) turn red
    chart_df_coc.loc[z_scores_coc >= 2, "Bar_Color"] = "#FF4B4B"

    # Latest bar also turns red if it's the highest in the window (ties count)
    if today_coc == max_coc:
        chart_df_coc.iloc[-1, chart_df_coc.columns.get_loc("Bar_Color")] = "#FF4B4B"

    st.bar_chart(
        data=chart_df_coc,
        x="Date",
        y="CoC Count",
        color="Bar_Color",
        use_container_width=True
    )

st.markdown("---")

# ═══════════════════ BREAKDOWN OF CHARACTER (Δ ≤ -20) ═══════════════════
st.markdown(f"#### 🔻 Breakdown of Character ({len(boc_today)})")

if boc_today or boc_yest:
    boc_industry_counts, boc_ticker_industry = build_leader_industry_map(boc_today, INDUSTRIES)

    html_boc = ""
    for sym in boc_today:  # alphabetical
        industries = boc_ticker_industry.get(sym, [])
        ranks = [industry_rank_map[ind] for ind in industries if ind in industry_rank_map]
        is_top20_industry = any(r <= 20 for r in ranks) if ranks else False
        glow_style = (
            "box-shadow:0 0 8px 2px #FF4B4B; border:1px solid #FF4B4B;"
            if is_top20_industry else ""
        )
        delta = boc_delta_map.get(sym, 0)
        score_val = boc_score_map.get(sym, 0)
        suffix = f"{score_val} ({delta})"  # delta already negative, no manual "-" needed
        html_boc += setup_badge(
            sym,
            is_new=(sym not in boc_yest),
            extra_style=glow_style,
            extra_suffix=suffix,
            extra_suffix_color="#8B0000",  # dark red
        )

    removed_boc = [sym for sym in boc_yest if sym not in boc_today]
    for sym in sorted(removed_boc):
        html_boc += f'<div class="ticker-badge removed-badge">{sym}</div>'

    st.markdown(html_boc, unsafe_allow_html=True)

    render_group_ai_insight(
        boc_today,
        "Breakdown of Character (Score drop ≥20)",
        "breakdown_of_character",
        extra_note="the stock's composite health score (RS-vs-benchmark, stage, trend, gap, and drawdown-symmetry checks) dropped by 20+ points day-over-day, signaling a fast-deteriorating technical picture / bearish character change"
    )
else:
    st.info("No active setups discovered.")

st.write("")
if not boc_hist.empty:
    chart_df_boc = boc_hist.copy()

    today_boc = chart_df_boc["BoC Count"].iloc[-1]
    max_boc   = chart_df_boc["BoC Count"].max()

    mean_boc = chart_df_boc["BoC Count"].mean()
    std_boc  = chart_df_boc["BoC Count"].std(ddof=1)

    if std_boc and std_boc > 0:
        z_scores_boc = (chart_df_boc["BoC Count"] - mean_boc) / std_boc
    else:
        z_scores_boc = pd.Series(0, index=chart_df_boc.index)

    # Default: every bar blue
    chart_df_boc["Bar_Color"] = "#29B5E8"

    # Statistical outliers (>=2 std dev above mean) turn red
    chart_df_boc.loc[z_scores_boc >= 2, "Bar_Color"] = "#FF4B4B"

    # Latest bar also turns red if it's the highest in the window (ties count)
    if today_boc == max_boc:
        chart_df_boc.iloc[-1, chart_df_boc.columns.get_loc("Bar_Color")] = "#FF4B4B"

    st.bar_chart(
        data=chart_df_boc,
        x="Date",
        y="BoC Count",
        color="Bar_Color",
        use_container_width=True
    )

# ============================================================
# BIGGEST UP / BIGGEST DOWN DAY — same formula as TML's score8 check
# (pct_chg.rolling(win).max()/.min(), win = min(220, len))
# Flags tickers where TODAY's % change equals its own rolling
# biggest-up or biggest-down day within that window.
# ============================================================
@st.cache_data(ttl=3600)
def compute_biggest_move_today(stocks_list, ticker_dfs):
    biggest_up_today = []
    biggest_down_today = []

    for ticker in stocks_list:
        try:
            df = ticker_dfs.get(ticker)
            if df is None or len(df) < 21:
                continue

            close = df['Close']
            pct_chg = close.pct_change() * 100
            win = min(220, len(pct_chg))

            biggest_drop = pct_chg.rolling(window=win, min_periods=20).min()
            biggest_up   = pct_chg.rolling(window=win, min_periods=20).max()

            today_chg  = pct_chg.iloc[-1]
            today_up   = biggest_up.iloc[-1]
            today_down = biggest_drop.iloc[-1]

            if pd.isna(today_chg) or pd.isna(today_up) or pd.isna(today_down):
                continue

            if today_chg >= today_up:
                biggest_up_today.append((ticker, round(float(today_chg), 2)))
            elif today_chg <= today_down:
                biggest_down_today.append((ticker, round(float(today_chg), 2)))

        except Exception:
            continue

    biggest_up_today.sort(key=lambda x: -x[1])
    biggest_down_today.sort(key=lambda x: x[1])

    return biggest_up_today, biggest_down_today


st.markdown("---")

with st.spinner("Scanning for biggest up/down day extremes..."):
    biggest_up_today, biggest_down_today = timed(
        "compute_biggest_move_today",
        compute_biggest_move_today,
        stocks_tuple, ticker_dfs_shared
    )

st.markdown(f"#### 📈📉 Biggest Move Today ({len(biggest_up_today)} vs {len(biggest_down_today)})")

col_up, col_down = st.columns(2)

with col_up:
    #st.markdown(f"**🟢 Biggest Up Day ({len(biggest_up_today)})**")
    if biggest_up_today:
        html_up = "<div style='display:flex;flex-wrap:wrap;gap:4px;padding:6px 0;'>"
        for sym, pct in biggest_up_today:
            html_up += (
                f'<div class="ticker-badge" style="background:#90EE90;border:1px solid #228B22;">'
                f'<span class="ticker-name" style="color:#003300;">{sym}</span>'
                f'<span class="ticker-rs" style="color:#003300;margin-left:4px;">+{pct:.1f}%</span>'
                f'</div>'
            )
        html_up += "</div>"
        st.markdown(html_up, unsafe_allow_html=True)
    else:
        st.info("None")

with col_down:
    #st.markdown(f"**🔴 Biggest Down Day ({len(biggest_down_today)})**")
    if biggest_down_today:
        html_down = "<div style='display:flex;flex-wrap:wrap;gap:4px;padding:6px 0;'>"
        for sym, pct in biggest_down_today:
            html_down += (
                f'<div class="ticker-badge" style="background:#FFB3B3;border:1px solid #CC0000;">'
                f'<span class="ticker-name" style="color:#4B0000;">{sym}</span>'
                f'<span class="ticker-rs" style="color:#4B0000;margin-left:4px;">{pct:.1f}%</span>'
                f'</div>'
            )
        html_down += "</div>"
        st.markdown(html_down, unsafe_allow_html=True)
    else:
        st.info("None")

@st.cache_data(ttl=3600)
def compute_biggest_move_history(stocks_list, ticker_dfs):
    """
    Vectorized daily count of tickers hitting a new rolling biggest-up-day
    or biggest-down-day (same win = min(220, len) logic as
    compute_biggest_move_today / TML's s8 component), evaluated across the
    full time series for a 60-day breadth history.
    """
    try:
        if not ticker_dfs:
            return pd.DataFrame()

        all_up_series = []
        all_down_series = []

        for ticker, df in ticker_dfs.items():
            if 'Close' not in df.columns or len(df) < 21:
                continue
            try:
                close = df['Close']
                pct_chg = close.pct_change() * 100
                win = min(220, len(pct_chg))

                biggest_up   = pct_chg.rolling(window=win, min_periods=20).max()
                biggest_drop = pct_chg.rolling(window=win, min_periods=20).min()

                up_flag   = (pct_chg >= biggest_up).astype(int)
                down_flag = (pct_chg <= biggest_drop).astype(int)

                all_up_series.append(up_flag)
                all_down_series.append(down_flag)
            except Exception:
                continue

        if not all_up_series:
            return pd.DataFrame()

        up_combined   = pd.concat(all_up_series, axis=1).fillna(0)
        down_combined = pd.concat(all_down_series, axis=1).fillna(0)

        up_counts   = up_combined.sum(axis=1)
        down_counts = down_combined.sum(axis=1)

        result = pd.DataFrame({
            "Date": up_counts.index,
            "Biggest Up Count": up_counts.values,
            "Biggest Down Count": down_counts.reindex(up_counts.index).values,
        }).tail(60)
        result["Date"] = pd.to_datetime(result["Date"]).dt.strftime("%Y-%m-%d")
        return result.reset_index(drop=True)
    except Exception:
        return pd.DataFrame()


st.write("")

with st.spinner("Scanning for Biggest Move History..."):
    biggest_move_hist = timed(
        "compute_biggest_move_history",
        compute_biggest_move_history,
        stocks_tuple, ticker_dfs_shared
    )

if not biggest_move_hist.empty:
    # --- Biggest Up Count chart ---
    chart_df_up = biggest_move_hist.copy()

    today_up_cnt = chart_df_up["Biggest Up Count"].iloc[-1]
    max_up_cnt   = chart_df_up["Biggest Up Count"].max()

    mean_up = chart_df_up["Biggest Up Count"].mean()
    std_up  = chart_df_up["Biggest Up Count"].std(ddof=1)

    if std_up and std_up > 0:
        z_scores_up = (chart_df_up["Biggest Up Count"] - mean_up) / std_up
    else:
        z_scores_up = pd.Series(0, index=chart_df_up.index)

    # Default: every bar blue
    chart_df_up["Bar_Color"] = "#29B5E8"

    # Statistical outliers (>=2 std dev above mean) turn red
    chart_df_up.loc[z_scores_up >= 2, "Bar_Color"] = "#FF4B4B"

    # Latest bar also turns red if it's the highest in the window (ties count)
    if today_up_cnt == max_up_cnt:
        chart_df_up.iloc[-1, chart_df_up.columns.get_loc("Bar_Color")] = "#FF4B4B"

    st.bar_chart(
        data=chart_df_up,
        x="Date",
        y="Biggest Up Count",
        color="Bar_Color",
        use_container_width=True
    )

    # --- Biggest Down Count chart ---
    chart_df_down = biggest_move_hist.copy()

    today_down_cnt = chart_df_down["Biggest Down Count"].iloc[-1]
    max_down_cnt   = chart_df_down["Biggest Down Count"].max()

    mean_down = chart_df_down["Biggest Down Count"].mean()
    std_down  = chart_df_down["Biggest Down Count"].std(ddof=1)

    if std_down and std_down > 0:
        z_scores_down = (chart_df_down["Biggest Down Count"] - mean_down) / std_down
    else:
        z_scores_down = pd.Series(0, index=chart_df_down.index)

    # Default: every bar blue
    chart_df_down["Bar_Color"] = "#29B5E8"

    # Statistical outliers (>=2 std dev above mean) turn red
    chart_df_down.loc[z_scores_down >= 2, "Bar_Color"] = "#FF4B4B"

    # Latest bar also turns red if it's the highest in the window (ties count)
    if today_down_cnt == max_down_cnt:
        chart_df_down.iloc[-1, chart_df_down.columns.get_loc("Bar_Color")] = "#FF4B4B"

    st.bar_chart(
        data=chart_df_down,
        x="Date",
        y="Biggest Down Count",
        color="Bar_Color",
        use_container_width=True
    )

# ==============================================================================
# UNUSUAL VOLUME — HVE (Highest Volume Ever) / HVQ (Highest Volume Quarter) / HVM (Highest Volume Month)
# Read-only: reuses ticker_dfs_shared (already fetched, ~2y history) and
# KNOWN_STOCKS. Does not touch any existing variable or function.
# ==============================================================================
@st.cache_data(ttl=3600)
def compute_unusual_volume(stocks_list, ticker_dfs, min_price=20, min_volume=100000):
    """
    For each ticker, flag today's bar if today's volume is the highest ever
    (HVE), highest in the trailing ~1 quarter / 63 trading days (HVQ), or
    highest in the trailing ~1 month / 21 trading days (HVM).
    HVE implies HVQ implies HVM, so a ticker is tagged with the STRONGEST
    flag it qualifies for (HVE > HVQ > HVM), not all three.
    Returns: dict of {"HVE": [...], "HVQ": [...], "HVM": [...]} — sorted lists,
    plus a dict of ticker -> today's volume for display.
    """
    hve_list, hvq_list, hvm_list = [], [], []
    vol_map = {}

    for ticker in stocks_list:
        try:
            df = ticker_dfs.get(ticker)
            if df is None or len(df) < 22:
                continue

            close = df['Close']
            vol   = df['Volume']

            today_close = close.iloc[-1]
            today_vol   = vol.iloc[-1]

            if pd.isna(today_close) or pd.isna(today_vol):
                continue
            if today_close < min_price or today_vol < min_volume:
                continue

            # Highest Volume Ever (entire available history, excludes current bar for the "prior max" check)
            hve_prior_max = vol.iloc[:-1].max() if len(vol) > 1 else 0
            is_hve = today_vol >= hve_prior_max

            # Highest Volume Quarter (trailing 63 trading days, excludes current bar)
            hvq_window = vol.iloc[-64:-1] if len(vol) >= 64 else vol.iloc[:-1]
            hvq_prior_max = hvq_window.max() if len(hvq_window) > 0 else 0
            is_hvq = today_vol >= hvq_prior_max

            # Highest Volume Month (trailing 21 trading days, excludes current bar)
            hvm_window = vol.iloc[-22:-1] if len(vol) >= 22 else vol.iloc[:-1]
            hvm_prior_max = hvm_window.max() if len(hvm_window) > 0 else 0
            is_hvm = today_vol >= hvm_prior_max

            vol_map[ticker] = int(today_vol)

            if is_hve:
                hve_list.append(ticker)
            elif is_hvq:
                hvq_list.append(ticker)
            elif is_hvm:
                hvm_list.append(ticker)

        except Exception:
            continue

    return {
        "HVE": sorted(hve_list),
        "HVQ": sorted(hvq_list),
        "HVM": sorted(hvm_list),
    }, vol_map


def _format_volume(v):
    if v >= 1_000_000:
        return f"{v/1_000_000:.1f}M"
    if v >= 1_000:
        return f"{v/1_000:.0f}K"
    return str(v)


with st.spinner("Scanning for unusual volume..."):
    unusual_vol_results, unusual_vol_map = timed(
        "compute_unusual_volume",
        compute_unusual_volume,
        stocks_tuple, ticker_dfs_shared
    )

hve_syms = unusual_vol_results["HVE"]
hvq_syms = unusual_vol_results["HVQ"]
hvm_syms = unusual_vol_results["HVM"]
total_unusual_vol = len(hve_syms) + len(hvq_syms) + len(hvm_syms)

#st.markdown(f"#### 📊 Unusual Volume ({total_unusual_vol})")

def _render_volume_badges(sym_list, vol_map):  # CHANGED: dropped badge_color_style param
    if not sym_list:
        st.info("None")
        return
    vol_industry_counts, vol_ticker_industry = build_leader_industry_map(sym_list, INDUSTRIES)  # NEW
    html_v = ""
    for sym in sym_list:
        # NEW: top-20 industry glow
        industries = vol_ticker_industry.get(sym, [])
        ranks = [industry_rank_map[ind] for ind in industries if ind in industry_rank_map]
        is_top20_industry = any(r <= 20 for r in ranks) if ranks else False
        glow_style = (
            "box-shadow:0 0 8px 2px #FF4B4B; border:1px solid #FF4B4B;"
            if is_top20_industry else ""
        )
        html_v += setup_badge(sym, extra_style=glow_style)  # CHANGED: base = precedence
    st.markdown(html_v, unsafe_allow_html=True)

st.markdown(f"**🔴 HVE ({len(hve_syms)})**")
_render_volume_badges(hve_syms, unusual_vol_map)  # CHANGED: removed style arg

st.write("")
st.markdown(f"**🟠 HVQ ({len(hvq_syms)})**")
_render_volume_badges(hvq_syms, unusual_vol_map)  # CHANGED: removed style arg

st.write("")
st.markdown(f"**🟡 HVM ({len(hvm_syms)})**")
_render_volume_badges(hvm_syms, unusual_vol_map)  # CHANGED: removed style arg

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


st.markdown("---")
st.markdown(
    "#### Pie Chart "
    "<span style='color:#888; font-size:12px;'>(Short term + Long term)</span>",
    unsafe_allow_html=True,
)

def compute_rsi(close_series, period=14):
    """Standard Wilder's RSI."""
    delta = close_series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi

# ETF daily direction pie chart at the bottom of the page
def _etf_pie_chart():
    etf_symbols = INDUSTRIES.get('ETF', [])
    if etf_symbols:
        etf_changes, etf_changes_pct, etf_latest_date, etf_market_caps = fetch_etf_daily_direction(tuple(etf_symbols))
        if etf_changes and etf_market_caps:
            labels = []
            values = []
            custom_text = []
            colors = []

            for sym in etf_symbols:
                cap = etf_market_caps.get(sym)
                if cap is None:
                    cap = 1.0
                pct = etf_changes_pct.get(sym, 0.0)
                direction = etf_changes.get(sym, 0.0)
                labels.append(sym)
                values.append(cap)
                custom_text.append(f"{pct:+.2f}%")
                colors.append('#00b894' if direction > 0 else '#d63031' if direction < 0 else '#95a5a6')

            # ── Identify the strongest and weakest ETF today ──
            strongest_idx = max(
                range(len(etf_symbols)),
                key=lambda i: etf_changes_pct.get(etf_symbols[i], float('-inf'))
            )
            weakest_idx = min(
                range(len(etf_symbols)),
                key=lambda i: etf_changes_pct.get(etf_symbols[i], float('inf'))
            )
            text_colors = [
                '#FFD700' if i in (strongest_idx, weakest_idx) else '#ffffff'
                for i in range(len(etf_symbols))
            ]

            fig = go.Figure(
                data=[go.Pie(
                    labels=labels,
                    values=values,
                    text=custom_text,
                    hole=0.4,
                    marker=dict(colors=colors, line=dict(color='#ffffff', width=1)),
                    sort=False,
                    textinfo='label+text',
                    textposition='inside',
                    insidetextorientation='radial',
                    showlegend=False,
                    textfont=dict(color=text_colors),
                    hovertemplate='%{label}<br>Daily Change: %{text}<br>Size: %{value:.2f}B<extra></extra>'
                )]
            )
            text_sizes = [12 if sym != 'XLB' else 11 for sym in labels]
            fig.update_traces(textfont=dict(size=text_sizes), pull=[0.02] * len(labels))

            positive_count = sum(1 for change in etf_changes.values() if change > 0)
            fig.update_layout(
                title={
                    'text': f"{positive_count}/10",
                    'x': 0.5,
                    'xanchor': 'center',
                    'font': {'size': 30}
                },
                margin=dict(l=0, r=0, t=50, b=0)
            )
            st.plotly_chart(fig, use_container_width=True)

            # ── 14-day RSI, sorted high to low ──
            rsi_rows = []
            for sym in etf_symbols:
                df_sym = ticker_dfs_shared.get(sym)
                if df_sym is None or len(df_sym) < 15:
                    continue
                rsi_series = compute_rsi(df_sym['Close'], period=14)
                rsi_val = rsi_series.iloc[-1]
                if pd.isna(rsi_val):
                    continue
                rsi_rows.append((sym, round(float(rsi_val), 1)))

            if rsi_rows:
                rsi_rows.sort(key=lambda x: -x[1])
                rsi_html = "<div style='display:flex;flex-wrap:wrap;justify-content:center;gap:4px;padding:6px 0;'>"
                for sym, rsi_val in rsi_rows:
                    pct = etf_changes_pct.get(sym, 0.0)
                    if pct > 0:
                        bg, border, txt = "#00FF00", "#009900", "#000000"
                    # elif rsi_val >= 70:
                    #     bg, border, txt = "#FFB3B3", "#CC0000", "#4B0000"
                    # elif rsi_val <= 30:
                    #     bg, border, txt = "#90EE90", "#228B22", "#003300"
                    else:
                        bg, border, txt = "#1e1e1e", "#444", "#eeeeee"
                    if sym == "XLK":
                        txt = "#ff0000"
                    rsi_html += (
                        f'<div class="ticker-badge" style="background:{bg}; border:1px solid {border};">'
                        f'<span class="ticker-name" style="color:{txt};">{sym}</span>'
                        #f'<span class="ticker-rs" style="color:{txt}; margin-left:4px;">{rsi_val:.1f}</span>'
                        f'</div>'
                    )
                rsi_html += "</div>"
                st.markdown(rsi_html, unsafe_allow_html=True)
        else:
            st.info('ETF daily direction data unavailable.')

    else:
        st.info('ETF ETF list unavailable.')

timed("ETF Pie Chart", _etf_pie_chart)

st.markdown("---")
st.markdown(
    "#### ETF Ratio "
    "<span style='color:#888; font-size:12px;'>(Long term)</span>",
    unsafe_allow_html=True,
)

def _relative_etf_ratios():
    ratio_pairs = (
        ("XLK", "SPY"),
        ("XLY", "XLP"),
        ("SPHB", "SPY"),
        ("IWM", "QQQ"),
        ("VUG", "VTV"),
        ("RSP", "SPY"),
        ("SMH", "IGV"),
    )

    #st.markdown("#### Relative ETF Ratios (1 Year)")
    ratio_chart_df = fetch_ratio_chart_data(ratio_pairs, period="1y")

    if not ratio_chart_df.empty:
        normalized_ratio_df = ratio_chart_df.divide(ratio_chart_df.iloc[0]).mul(100)

        fig = go.Figure()
        annotations = []
        for ratio_name in normalized_ratio_df.columns:
            y_values = normalized_ratio_df[ratio_name]
            fig.add_trace(
                go.Scatter(
                    x=normalized_ratio_df.index,
                    y=y_values,
                    mode="lines",
                    name=ratio_name,
                    showlegend=False,
                    hovertemplate=f"{ratio_name}<br>%{{x|%Y-%m-%d}}<br>Indexed: %{{y:.2f}}<extra></extra>"
                )
            )

            # Highlight label if the latest value is a new high or new low for the period
            is_new_high = y_values.iloc[-1] > y_values.iloc[:-1].max()
            is_new_low = y_values.iloc[-1] < y_values.iloc[:-1].min()
            label_color = "lime" if is_new_high else "red" if is_new_low else "white"

            annotations.append(
                dict(
                    x=normalized_ratio_df.index[-1],
                    y=y_values.iloc[-1],
                    xref="x",
                    yref="y",
                    text=ratio_name,
                    xanchor="left",
                    yanchor="middle",
                    showarrow=False,
                    font=dict(size=11, color=label_color),
                    bgcolor="rgba(0,0,0,0.5)",
                    bordercolor="rgba(0,0,0,0.1)",
                    borderwidth=1,
                    borderpad=2
                )
            )

        fig.add_hline(
            y=100,
            line_width=3,
            line_color="white",
            layer="above"
        )

        fig.update_layout(
            height=420,
            margin=dict(l=0, r=120, t=10, b=0),
            yaxis_title="Indexed to 100",
            xaxis_title=None,
            hovermode="x unified",
            annotations=annotations
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Relative ETF ratio data unavailable.")

timed("Relative ETF Ratios", _relative_etf_ratios)

st.markdown("---")

# ── Timing Summary ───────────────────────────────────────────────────────────
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

# ============================================================
# QUANT SENTIMENT — Trending Stocks (stockanalysis.com)
# ============================================================
@st.cache_data(ttl=3600)
def fetch_trending_stocks_today():
    """Fetch trending tickers from stockanalysis.com/trending/ with Market Cap >= $1B"""

    url = "https://stockanalysis.com/trending/"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }

    def parse_market_cap(cap_str):
        """
        Convert market cap string into numeric value.

        Examples:
        2.44T  -> 2440000000000
        323.5B -> 323500000000
        850M   -> 850000000
        """
        try:
            cap_str = cap_str.strip().upper()

            if not cap_str or cap_str == "-":
                return 0

            if cap_str.endswith("T"):
                return float(cap_str[:-1]) * 1_000_000_000_000

            if cap_str.endswith("B"):
                return float(cap_str[:-1]) * 1_000_000_000

            if cap_str.endswith("M"):
                return float(cap_str[:-1]) * 1_000_000

            return float(cap_str)

        except Exception:
            return 0

    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.content, "html.parser")

        # Primary table
        table = soup.find("table", {"id": "main-table"})

        # Fallback
        if table is None:
            table = soup.find("table")

        if table is None:
            return []

        # --------------------------------------------------
        # Find column positions dynamically
        # --------------------------------------------------
        headers_row = table.find("tr")

        if not headers_row:
            return []

        header_cells = headers_row.find_all(["th", "td"])

        symbol_idx = None
        marketcap_idx = None

        for idx, cell in enumerate(header_cells):
            txt = cell.get_text(strip=True)

            if txt == "Symbol":
                symbol_idx = idx

            elif "Market Cap" in txt:
                marketcap_idx = idx

        # Fallback to current StockAnalysis layout
        if symbol_idx is None:
            symbol_idx = 1

        if marketcap_idx is None:
            marketcap_idx = 4

        # --------------------------------------------------
        # Parse rows
        # --------------------------------------------------
        symbols = []
        seen = set()

        for row in table.find_all("tr"):
            cells = row.find_all("td")

            if not cells:
                continue

            max_required_idx = max(symbol_idx, marketcap_idx)

            if len(cells) <= max_required_idx:
                continue

            raw_symbol = cells[symbol_idx].get_text(strip=True).upper()

            symbol = "".join(
                c for c in raw_symbol
                if c.isalpha() or c == "-"
            ).strip()

            symbol = normalize_ticker(symbol)

            market_cap_text = cells[marketcap_idx].get_text(strip=True)
            market_cap = parse_market_cap(market_cap_text)

            # ==================================================
            # FILTER: Market Cap must be at least $1 Billion
            # ==================================================
            if market_cap < 1_000_000_000:
                continue

            if symbol and symbol not in seen:
                seen.add(symbol)
                symbols.append(symbol)

            if len(symbols) >= 50:
                break

        return symbols

    except Exception as e:
        st.warning(f"Quant Sentiment: could not fetch trending stocks — {e}")
        return []

def _github_headers():
    token = st.secrets.get("GITHUB_TOKEN")
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }

def _github_filepath(date_obj):
    return f"trending_history/trending_{date_obj.isoformat()}.txt"

def save_trending_list_github(date_obj, tickers):
    """Commit today's trending tickers to the GitHub data repo (creates or updates)."""
    repo   = st.secrets.get("GITHUB_REPO")
    branch = st.secrets.get("GITHUB_BRANCH", "main")

    if not repo or not st.secrets.get("GITHUB_TOKEN"):
        st.warning("GitHub secrets (GITHUB_TOKEN / GITHUB_REPO) not configured — skipping save.")
        return

    path = _github_filepath(date_obj)
    url  = f"{GITHUB_API}/repos/{repo}/contents/{path}"

    content_str = "\n".join(tickers)
    content_b64 = base64.b64encode(content_str.encode()).decode()

    # Check if a file already exists for this date (need its sha to overwrite)
    sha = None
    try:
        resp = requests.get(url, headers=_github_headers(), params={"ref": branch}, timeout=10)
        if resp.status_code == 200:
            sha = resp.json().get("sha")
    except Exception:
        pass

    payload = {
        "message": f"Trending snapshot {date_obj.isoformat()}",
        "content": content_b64,
        "branch": branch,
    }
    if sha:
        payload["sha"] = sha  # required when overwriting an existing file

    try:
        put_resp = requests.put(url, headers=_github_headers(), json=payload, timeout=10)
        if put_resp.status_code not in (200, 201):
            st.warning(f"GitHub save failed: {put_resp.status_code} {put_resp.text[:150]}")
    except Exception as e:
        st.warning(f"GitHub save error: {e}")

@st.cache_data(ttl=3600)
def load_trending_list_github(date_obj):
    """Load tickers for an exact date from GitHub. Returns None if not found."""
    repo   = st.secrets.get("GITHUB_REPO")
    branch = st.secrets.get("GITHUB_BRANCH", "main")

    if not repo or not st.secrets.get("GITHUB_TOKEN"):
        return None

    path = _github_filepath(date_obj)
    url  = f"{GITHUB_API}/repos/{repo}/contents/{path}"

    try:
        resp = requests.get(url, headers=_github_headers(), params={"ref": branch}, timeout=10)
        if resp.status_code != 200:
            return None
        data = resp.json()
        decoded = base64.b64decode(data["content"]).decode()
        return [line.strip() for line in decoded.splitlines() if line.strip()]
    except Exception:
        return None

@st.cache_data(ttl=3600)
def find_nearest_backward_trending_list_github(start_date, max_lookback_days=30):
    """
    Walk backward from start_date (exclusive) day by day until a saved
    trending file is found in the GitHub data repo.
    Returns (tickers, date_found) or ([], None) if nothing found within the lookback window.
    """
    for i in range(1, max_lookback_days + 1):
        check_date = start_date - datetime.timedelta(days=i)
        tickers = load_trending_list_github(check_date)
        if tickers is not None:
            return tickers, check_date
    return [], None


# ── Fetch today's list, persist to GitHub, find comparison baseline ─────────
today_date = datetime.date.today()

trending_today = timed("fetch_trending_stocks_today", fetch_trending_stocks_today)

if trending_today:
    timed("save_trending_list_github", save_trending_list_github, today_date, trending_today)

trending_yesterday, comparison_date = timed(
    "find_nearest_backward_trending_list_github",
    find_nearest_backward_trending_list_github,
    today_date
)
yesterday_set = set(trending_yesterday)

# ── Render section ────────────────────────────────────────────────────────────
st.markdown("---")

comparison_label = comparison_date.isoformat() if comparison_date else "no prior data"
st.markdown(
    f"#### 📡 Quant Sentiment "
    f"<span style='color:#888; font-size:12px;'>(vs {comparison_label})</span>",
    unsafe_allow_html=True,
)

if trending_today:
    # Build one HTML row preserving the ranked order from the table
    qs_html = "<div style='display:flex; flex-wrap:wrap; gap:4px; padding:6px 0;'>"

    for rank, sym in enumerate(trending_today, start=1):
        is_new = sym not in yesterday_set

        # Colour logic: gold if new, lime if also in LIME_STOCKS,
        # gold-on-black (known) if in KNOWN_STOCKS, else default dark badge
        if is_new:
            badge_style = (
                "background:#FFD700; border:1px solid #B8860B; color:#111111; font-weight:bold;"
            )
        # elif sym in LIME_STOCKS:
        #     badge_style = (
        #         "background:#00FF00; border:1px solid #009900; color:#000000; font-weight:bold;"
        #     )
        # elif sym in KNOWN_STOCKS:
        #     badge_style = (
        #         "background:#1e1e1e; border:1px solid #FFD700; color:#FFD700; font-weight:bold;"
        #     )
        else:
            badge_style = (
                "background:#1e1e1e; border:1px solid #444; color:#FFFFFF; font-weight:bold;"
            )

        glow_style = (
            "box-shadow:0 0 8px 2px #FFD700;"
            if sym not in KNOWN_STOCKS else ""
        )

        qs_html += (
            f"<div style='display:inline-flex; align-items:center; gap:4px; "
            f"padding:2px 7px; border-radius:3px; font-size:12px; "
            f"white-space:nowrap; {badge_style} {glow_style}'>"
            f"<span style='font-weight:bold; color:inherit;'>{sym}</span>"
            #f"{'<span style=\"font-size:9px;\">★</span>' if is_new else ''}"
            f"</div>"
        )

    qs_html += "</div>"

    st.markdown(qs_html, unsafe_allow_html=True)

else:
    st.info("Quant Sentiment: no trending data available right now.")

#st.markdown("---")

@st.cache_data(ttl=3600)
def fetch_reddit_mentions_apewisdom(stocks_tuple, filter_type="wallstreetbets"):
    """
    filter_type options: 'all-stocks', 'wallstreetbets', 'stocks', 'investing', 'options', etc.
    Returns top mentioned tickers from the last 24h (all tickers, not just KNOWN_STOCKS).
    """
    def safe_int(v, default=0):
        try:
            return int(v)
        except (TypeError, ValueError):
            return default

    rows = []
    page = 1

    try:
        while True:
            resp = requests.get(
                f"https://apewisdom.io/api/v1.0/filter/{filter_type}/page/{page}",
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", [])
            if not results:
                break

            for r in results:
                ticker = r.get("ticker")
                if not ticker:
                    continue
                rows.append({
                    "Ticker": ticker,
                    "Rank": safe_int(r.get("rank")),
                    "Mentions": safe_int(r.get("mentions")),
                    "Mentions 24h Ago": safe_int(r.get("mentions_24h_ago")),
                    "Upvotes": safe_int(r.get("upvotes")),
                })

            if page >= safe_int(data.get("pages"), 1):
                break
            page += 1

    except Exception as e:
        st.warning(f"ApeWisdom fetch error: {e}")
        return pd.DataFrame()

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df["Ticker"] = df["Ticker"].apply(normalize_ticker)

    # If normalization caused two rows to collapse onto the same
    # ticker (e.g. both GOOG and GOOGL were trending separately),
    # aggregate them into a single row instead of leaving duplicates:
    # sum mention counts, keep the best (lowest) rank, sum upvotes.
    df = (
        df.groupby("Ticker", as_index=False)
        .agg({
            "Rank": "min",
            "Mentions": "sum",
            "Mentions 24h Ago": "sum",
            "Upvotes": "sum",
        })
    )

    df["Δ Mentions"] = df["Mentions"] - df["Mentions 24h Ago"]
    return df.sort_values("Mentions", ascending=False).reset_index(drop=True)

with st.spinner("Fetching Reddit sentiment..."):
    reddit_df = timed(
        "fetch_reddit_mentions_apewisdom",
        fetch_reddit_mentions_apewisdom,
        stocks_tuple, "wallstreetbets"
    )

#st.markdown(f"#### 🧵 Reddit ({len(reddit_df)})")
st.markdown(
    f"""
    <div style="display:flex; align-items:center; gap:8px; margin-top:22px; margin-bottom:6px;">
        <img src="https://www.redditstatic.com/desktop2x/img/favicon/android-icon-192x192.png"
             style="width:24px; height:24px; vertical-align:middle;">
        <span style="font-size:1.5em; font-weight:600; color:#ffffff;">
            Reddit
        </span>
    </div>
    """,
    unsafe_allow_html=True
)

if reddit_df.empty:
    st.info("No mentions found on Reddit right now.")
else:
    reddit_df_display = reddit_df[~reddit_df["Ticker"].isin(["SPY", "QQQ", "VOO"])]
    html_reddit = ""
    for _, row in reddit_df_display.head(30).iterrows():
        sym = row["Ticker"]
        delta = row["Δ Mentions"]
        delta_color = "#00FF00" if delta > 0 else "#FF4B4B" if delta < 0 else "#888888"
        delta_str = f"+{delta}" if delta > 0 else str(delta)

        glow_style = (
            "box-shadow:0 0 8px 2px #FFD700; border:1px solid #FFD700;"
            if sym not in KNOWN_STOCKS else ""
        )

        html_reddit += (
            f'<div class="ticker-badge" style="{glow_style}">'
            f'<span class="ticker-name">{sym}</span>'
            f'<span class="ticker-rs" style="color:#378ADD;">{row["Mentions"]} </span>'
            f'<span style="color:{delta_color}; margin-left:5px; font-size:12px;">({delta_str})</span>'
            f'</div>'
        )
    st.markdown(html_reddit, unsafe_allow_html=True)
    st.write("")

    # with st.expander("Full table"):
    #     st.dataframe(reddit_df, use_container_width=False, width=500, hide_index=True)

    # # ── Common tickers between Quant Sentiment (trending) and Reddit ──
    # common_syms = sorted(set(trending_today) & set(reddit_df_display["Ticker"]))
    # st.markdown(
    #     f"**🔗 In Common: {len(common_syms)}**"
    # )
    # if common_syms:
    #     common_html = "<div style='display:flex;flex-wrap:wrap;gap:4px;padding:6px 0;'>"
    #     for sym in common_syms:
    #         common_html += (
    #             f'<div class="ticker-badge" style="background:#1E1E1E; border:1px solid #444; color:#FFFFFF; font-weight:bold;">'
    #             f'<span>{sym}</span></div>'
    #         )
    #     common_html += "</div>"
    #     st.markdown(common_html, unsafe_allow_html=True)
    # else:
    #     st.info("No overlap between trending and Reddit lists.")

@st.cache_data(ttl=3600)
def fetch_spikepanel_surge_tickers(window="24h"):
    """
    Fetch the ranked list of tickers from SpikePanel's '热议' (Hot Discussion)
    page: https://spikepanel.com/surge

    window: "latest" | "24h" | "7d" | "30d" — maps to the tabs on the page.
    Returns a list of up to 20 tickers, in the same rank order shown on
    the page (rank #1 first).
    """
    url = "https://spikepanel.com/surge"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }

    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        html = resp.text
    except Exception as e:
        st.warning(f"SpikePanel fetch error: {e}")
        return []

    # Every stock card links to /ticker/{SYMBOL}?from=surge — this pattern
    # is stable regardless of CSS/markup changes, and both the main list
    # and the compact re-render on the page use the same href, so we
    # dedupe while preserving first-seen (i.e. rank) order.
    matches = re.findall(r'/ticker/([A-Z][A-Z0-9\.\-]{0,6})\?from=surge', html)

    seen = set()
    tickers = []
    for raw_sym in matches:
        sym = normalize_ticker(raw_sym)
        if sym and sym not in seen:
            seen.add(sym)
            tickers.append(sym)

    # Page shows exactly 20 ranked stocks — trim defensively in case the
    # dedupe above ever lets extra unrelated /ticker/ links slip through.
    return tickers[:20]

spikepanel_tickers = fetch_spikepanel_surge_tickers()

st.markdown(f"#### 🧵 X.com")#({len(spikepanel_tickers)})

if spikepanel_tickers:
    badges_html = "<div style='display:flex; flex-wrap:wrap; gap:6px; margin-top:6px;'>"
    for sym in spikepanel_tickers:
        badges_html += (
            f"<span style='display:inline-block; padding:2px 6px; border:1px solid #444; "
            f"border-radius:4px; background-color:#1e1e1e; color:#eee; font-size:12px; "
            f"white-space:nowrap;'>{sym}</span>"
        )
    badges_html += "</div>"
    st.markdown(badges_html, unsafe_allow_html=True)
else:
    st.info("None")

# ==============================================================================
# IBD "STOCK MARKET TODAY" — TICKER EXTRACTION FROM LATEST YOUTUBE VIDEO
# Read-only scrape of IBD's YouTube Streams tab. Skips videos whose title
# doesn't contain "Stock Market Today", extracts tickers from the first
# matching (latest) video. Does not touch any existing variable/function.
# ==============================================================================

IBD_CHANNEL_HANDLE_URL = "https://www.youtube.com/@investorsbusinessdaily"
IBD_STREAMS_URL = "https://www.youtube.com/@investorsbusinessdaily/streams"

# Common all-caps words to exclude from the fallback ticker scan
_TICKER_STOPWORDS = {
    "IBD", "ETF", "ETFS", "CEO", "CFO", "USA", "US", "AI", "IPO", "GDP",
    "FED", "SEC", "NYSE", "NASDAQ", "PE", "EPS", "ATH", "ATR", "RS",
    "MA", "SMA", "EMA", "TV", "YOY", "QOQ", "S&P", "DOW",
}

def _extract_tickers_from_ibd_title(title):
    """
    Primary: capture comma-separated ALL-CAPS tickers immediately before a
    common IBD trigger phrase ('In Focus', 'Near Buy Point', etc.), matching
    the "GH, FCX, SPHR In Focus | Stock Market Today" pattern.
    Fallback: scan for standalone 1-5 letter all-caps tokens, stopword-filtered.
    """
    if not title:
        return []

    trigger_phrases = [
        r"In Focus", r"Near Buy Points?", r"Buy Points?", r"Eyed",
        r"On Watch", r"In Play", r"Flash(?:es)? Buy Signal",
    ]
    trigger_pattern = "|".join(trigger_phrases)

    match = re.search(
        r"([A-Z][A-Z0-9\.\-]{0,5}(?:\s*,\s*[A-Z][A-Z0-9\.\-]{0,5}){0,6})\s+(?:" + trigger_pattern + r")",
        title,
    )

    if match:
        candidates = [t.strip() for t in match.group(1).split(",")]
    else:
        candidates = re.findall(r"\b[A-Z]{1,5}\b", title)

    tickers, seen = [], set()
    for tok in candidates:
        tok = tok.strip().upper()
        if not tok or tok in _TICKER_STOPWORDS or tok in seen:
            continue
        if not re.fullmatch(r"[A-Z]{1,5}", tok):
            continue
        seen.add(tok)
        tickers.append(tok)

    return tickers

@st.cache_data(ttl=86400)
def _resolve_tickers_via_ai_from_title(title):
    """Fallback: when the title uses full company names instead of tickers,
    ask an AI to return ONLY the ticker symbols, comma-separated."""
    if not title:
        return []

    prompt = (
        "Based on the YouTube video title below, give me the 3 stock tickers "
        "which are most likely being referenced. Only output the stock "
        "tickers separated by commas, nothing else — no explanation, no "
        "extra words, no numbering.\n\n"
        f"Title: {title}"
    )

    def _parse(text):
        if not text:
            return []
        tokens = re.split(r"[,\s]+", text.strip())
        out, seen = [], set()
        for tok in tokens:
            tok = tok.strip().upper().strip(".")
            if re.fullmatch(r"[A-Z]{1,5}", tok) and tok not in seen and tok not in _TICKER_STOPWORDS:
                seen.add(tok)
                out.append(tok)
        return out

    for gemini_key, gemini_model in [
        (st.secrets.get("GEMINI_API_KEY"), "gemini-2.5-flash"),
        (st.secrets.get("GEMINI_API_KEY_2"), "gemini-3.5-flash"),
    ]:
        if not gemini_key:
            continue
        try:
            from google import genai as google_genai
            client = google_genai.Client(api_key=gemini_key)
            response = client.models.generate_content(model=gemini_model, contents=prompt)
            tickers = _parse(response.text)
            if tickers:
                return tickers
        except Exception:
            continue

    groq_key = st.secrets.get("GROQ_API_KEY")
    if groq_key:
        try:
            from openai import OpenAI as OpenAIClient
            groq_client = OpenAIClient(api_key=groq_key, base_url="https://api.groq.com/openai/v1")
            completion = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=100, temperature=0.1,
            )
            tickers = _parse(completion.choices[0].message.content)
            if tickers:
                return tickers
        except Exception:
            pass

    openrouter_key = st.secrets.get("OPENROUTER_API_KEY")
    if openrouter_key:
        try:
            from openai import OpenAI as OpenAIClient
            or_client = OpenAIClient(
                api_key=openrouter_key, base_url="https://openrouter.ai/api/v1",
                default_headers={"HTTP-Referer": "https://your-app-name.streamlit.app", "X-Title": "Theme Tracker"},
            )
            completion = or_client.chat.completions.create(
                model="meta-llama/llama-3.1-8b-instruct:free",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=100, temperature=0.1,
            )
            tickers = _parse(completion.choices[0].message.content)
            if tickers:
                return tickers
        except Exception:
            pass

    github_token = st.secrets.get("GITHUB_MODELS_TOKEN")
    if github_token:
        try:
            from openai import OpenAI as OpenAIClient
            github_client = OpenAIClient(api_key=github_token, base_url="https://models.inference.ai.azure.com")
            completion = github_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=100, temperature=0.1,
            )
            tickers = _parse(completion.choices[0].message.content)
            if tickers:
                return tickers
        except Exception:
            pass

    return []

@st.cache_data(ttl=86400)
def _resolve_ibd_channel_id():
    """Resolve the stable UC... channel ID behind the @investorsbusinessdaily handle.
    Tries multiple extraction patterns since YouTube's HTML varies by request context.
    Cached 24h since a channel's ID never changes."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }

    for url in (IBD_STREAMS_URL, IBD_CHANNEL_HANDLE_URL):
        try:
            resp = requests.get(url, headers=headers, cookies={"CONSENT": "YES+1"}, timeout=15)
            resp.raise_for_status()
            html = resp.text
        except Exception:
            continue

        for pattern in (
            r'"channelId":"(UC[a-zA-Z0-9_-]{22})"',
            r'"externalId":"(UC[a-zA-Z0-9_-]{22})"',
            r'"browseId":"(UC[a-zA-Z0-9_-]{22})"',
            r'channel/(UC[a-zA-Z0-9_-]{22})',
        ):
            m = re.search(pattern, html)
            if m:
                return m.group(1)

    return None


@st.cache_data(ttl=3600)
def fetch_ibd_stock_market_today_tickers(max_videos_to_scan=25):
    """
    Fetch IBD's latest uploads via YouTube's public RSS feed, find the latest
    video whose title contains 'Stock Market Today', and return its tickers.
    Also returns the raw scanned titles for debugging if no match is found.
    """
    import xml.etree.ElementTree as ET

    channel_id = _resolve_ibd_channel_id()
    if not channel_id:
        return {"error": "Could not resolve IBD's YouTube channel ID."}

    rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
    }

    try:
        resp = requests.get(rss_url, headers=headers, cookies={"CONSENT": "YES+1"}, timeout=15)
        resp.raise_for_status()
        xml_text = resp.text
    except Exception as e:
        return {"error": f"RSS fetch error: {e}", "channel_id": channel_id}

    try:
        root = ET.fromstring(xml_text)
    except Exception as e:
        return {"error": f"RSS parse error: {e}", "channel_id": channel_id}

    ns = {
        "atom": "http://www.w3.org/2005/Atom",
        "yt": "http://www.youtube.com/xml/schemas/2015",
    }

    videos = []
    for entry in root.findall("atom:entry", ns):
        title_el = entry.find("atom:title", ns)
        vid_el = entry.find("yt:videoId", ns)
        if title_el is None or vid_el is None:
            continue
        title_text = (title_el.text or "").strip()
        vid = vid_el.text or ""
        if title_text and vid:
            videos.append({"videoId": vid, "title": title_text})

    if not videos:
        return {"error": "RSS feed returned no videos.", "channel_id": channel_id}

    for video in videos[:max_videos_to_scan]:
        title = video["title"]
        if "stock market today" in title.lower():
            tickers = _resolve_tickers_via_ai_from_title(title)   # AI first — handles company names + false-positive acronyms
            if not tickers:
                tickers = _extract_tickers_from_ibd_title(title)  # regex fallback only if every AI provider fails
            return {
                "tickers": tickers,
                "title": title,
                "video_id": video["videoId"],
                "video_url": f"https://www.youtube.com/watch?v={video['videoId']}",
                "channel_id": channel_id,
            }

    return {
        "error": "No recent video with 'Stock Market Today' in title found.",
        "channel_id": channel_id,
        "scanned_titles": [v["title"] for v in videos[:max_videos_to_scan]],
    }

# ── Render section ────────────────────────────────────────────────────────
#st.markdown("---")
st.write("")
st.markdown(
    "#### 🎓 IBD "
    "<span style='color:#888; font-size:12px;'>(Youtube Live)</span>",
    unsafe_allow_html=True,
)

with st.spinner("Checking IBD's latest Stock Market Today video..."):
    ibd_result = timed(
        "fetch_ibd_stock_market_today_tickers",
        fetch_ibd_stock_market_today_tickers,
    )

if ibd_result.get("error"):
    st.info(f"Unable to fetch IBD video data — {ibd_result['error']}")
    if ibd_result.get("channel_id"):
        st.caption(f"Resolved channel ID: `{ibd_result['channel_id']}`")
    if ibd_result.get("scanned_titles"):
        with st.expander("Debug: titles scanned from RSS feed"):
            for t in ibd_result["scanned_titles"]:
                st.write(f"- {t}")
else:
    st.markdown(f"**[{ibd_result['title']}]({ibd_result['video_url']})**")

    tickers_found = ibd_result.get("tickers", [])
    if tickers_found:
        ibd_industry_counts, ibd_ticker_industry = build_leader_industry_map(tickers_found, INDUSTRIES)  # NEW
        html_ibd = "<div style='display:flex;flex-wrap:wrap;gap:4px;padding:6px 0;'>"
        for sym in tickers_found:
            # NEW: top-20 industry glow
            industries = ibd_ticker_industry.get(sym, [])
            ranks = [industry_rank_map[ind] for ind in industries if ind in industry_rank_map]
            is_top20_industry = any(r <= 20 for r in ranks) if ranks else False
            glow_style = (
                "box-shadow:0 0 8px 2px #FF4B4B; border:1px solid #FF4B4B;"
                if is_top20_industry else ""
            )
            # setup_badge precedence: 50ma_bounce > aqua > purple > gold(known) > default
            html_ibd += setup_badge(sym, is_new=(sym in KNOWN_STOCKS), extra_style=glow_style)  # CHANGED
        html_ibd += "</div>"
        st.markdown(html_ibd, unsafe_allow_html=True)
    else:
        st.info("No tickers could be extracted from the title.")

# ==============================================================================
# IBD STOCK OF THE DAY — TICKER EXTRACTION
# Read-only scrape of investors.com's "IBD Stock Of The Day" category page.
# Extracts tickers via cashtag ($XYZ), exchange-prefixed (NASDAQ:XYZ), and
# KNOWN_STOCKS whitelist matching as a fallback. Does not touch any
# existing variable/function.
# ==============================================================================

IBD_STOCK_OF_DAY_URL = "https://www.investors.com/category/research/ibd-stock-of-the-day/"

# Tickers that are valid symbols but are also common English words/acronyms
# that create false positives in title text (e.g. "AI" in "Artificial
# Intelligence"). Extend this set freely — it's a display-level exclusion,
# not extraction logic, so it never needs per-company hardcoding.
IBD_SOTD_EXCLUDE_TICKERS = {"AI"}


def _extract_tickers_from_ibd_sotd_text(text_blob, restrict_to_known=None):
    """
    Extract candidate tickers from a block of text using three patterns,
    in priority order:
      1. Cashtag: $NVDA
      2. Exchange-prefixed: (NASDAQ:NVDA) / (NYSE:NVDA)
      3. Whitelist match: any all-caps 1-5 letter token that also appears
         in restrict_to_known (your KNOWN_STOCKS universe).
    Applies IBD_SOTD_EXCLUDE_TICKERS as a final filter on all three.
    Returns a de-duplicated, order-preserved list.
    """
    if not text_blob:
        return []

    tickers, seen = [], set()

    for m in re.finditer(r"\$([A-Z]{1,5})\b", text_blob):
        tok = m.group(1).upper()
        if tok not in seen and tok not in IBD_SOTD_EXCLUDE_TICKERS:
            seen.add(tok)
            tickers.append(tok)

    for m in re.finditer(r"\((?:NASDAQ|NYSE|NYSEARCA|AMEX)\s*:\s*([A-Z]{1,5})\)", text_blob):
        tok = m.group(1).upper()
        if tok not in seen and tok not in IBD_SOTD_EXCLUDE_TICKERS:
            seen.add(tok)
            tickers.append(tok)

    if restrict_to_known:
        for m in re.finditer(r"\b[A-Z]{1,5}\b", text_blob):
            tok = m.group(0).upper()
            if tok in restrict_to_known and tok not in seen and tok not in IBD_SOTD_EXCLUDE_TICKERS:
                seen.add(tok)
                tickers.append(tok)

    return tickers


def _extract_company_name_candidates_from_ibd_title(title):
    """
    Extract candidate company-name phrases from an IBD 'Stock Of The Day'
    title, generically (no per-company hardcoding). Returns a list of
    candidate phrases to try resolving, ordered most-to-least specific —
    the resolver will try each one via progressive word-trimming.
    """
    if not title:
        return []

    candidates = []

    # "<optional How >Company Name, [Day's ]IBD Stock Of The Day, ..."
    m = re.search(
        r"^(?:How\s+)?(.+?),\s*(?:\w+(?:'s)?\s+)?(?:IBD\s+)?Stock\s+Of\s+The\s+Day\b",
        title,
        re.IGNORECASE,
    )
    if m and m.group(1).strip():
        candidates.append(m.group(1).strip())

    # "IBD Stock Of The Day: Company Name Rises/Breaks Out/..."
    m = re.search(
        r"(?:IBD\s+)?Stock\s+Of\s+The\s+Day\s*:\s*(.+)$",
        title,
        re.IGNORECASE,
    )
    if m and m.group(1).strip():
        candidates.append(m.group(1).strip())

    return candidates


def _progressive_word_trims(phrase, max_words=4):
    """
    Given a captured phrase (which may have trailing verbs/description
    words glued on, e.g. 'Datadog Breaks Out Above Buy Point'), generate
    progressively shorter leading-word candidates to try:
      ['Datadog Breaks Out Above', 'Datadog Breaks Out', 'Datadog Breaks', 'Datadog']
    Purely mechanical word-count trimming — no company-specific logic.
    """
    if not phrase:
        return []
    words = phrase.strip().split()
    words = words[:max_words] if len(words) > max_words else words
    out = []
    for n in range(len(words), 0, -1):
        out.append(" ".join(words[:n]))
    return out


def _extract_company_name_from_ibd_url(url):
    """Fallback: guess a company name from the investors.com URL slug."""
    if not url:
        return None
    m = re.search(r"ibd-stock-of-the-day/([a-z0-9\-]+)-stock-", url, re.IGNORECASE)
    if not m:
        return None
    slug = m.group(1).replace("-", " ").strip()
    return slug if slug else None


@st.cache_data(ttl=86400)
def _resolve_name_via_yahoo(name_candidate):
    """Try resolving one name candidate to a ticker via Yahoo Finance search."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
    }
    try:
        resp = requests.get(
            "https://query1.finance.yahoo.com/v1/finance/search",
            params={"q": name_candidate, "quotesCount": 6, "newsCount": 0},
            headers=headers,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return []

    quotes = data.get("quotes", []) if isinstance(data, dict) else []
    out = []
    for q in quotes:
        symbol = q.get("symbol", "")
        if symbol and q.get("quoteType") == "EQUITY" and "." not in symbol:
            out.append(symbol.upper())
    return out


@st.cache_data(ttl=86400)
def _resolve_name_via_fmp(name_candidate):
    """Fallback resolver: Financial Modeling Prep's ticker search (uses your existing FMP_API_KEY)."""
    fmp_key = st.secrets.get("FMP_API_KEY")
    if not fmp_key:
        return []
    try:
        resp = requests.get(
            "https://financialmodelingprep.com/api/v3/search",
            params={"query": name_candidate, "limit": 6, "exchange": "NASDAQ,NYSE", "apikey": fmp_key},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    out = []
    for item in data:
        symbol = item.get("symbol", "")
        if symbol and "." not in symbol:
            out.append(symbol.upper())
    return out


@st.cache_data(ttl=86400)
def _resolve_company_name_to_ticker(company_name, known_universe_tuple=None):
    """
    Resolve a company name to its ticker, generically: tries progressively
    shorter leading-word trims of the name (handles trailing description
    words glued onto the captured phrase), across two independent resolvers
    (Yahoo Finance, then FMP as fallback). Prefers a result already in
    known_universe_tuple (your KNOWN_STOCKS) when multiple candidates exist.
    Returns None if nothing resolves.
    """
    if not company_name:
        return None

    known_set = set(known_universe_tuple) if known_universe_tuple else set()
    trims = _progressive_word_trims(company_name, max_words=4)

    for trim in trims:
        for resolver in (_resolve_name_via_yahoo, _resolve_name_via_fmp):
            candidates = resolver(trim)
            if not candidates:
                continue
            candidates = [c for c in candidates if c not in IBD_SOTD_EXCLUDE_TICKERS]
            if not candidates:
                continue
            for c in candidates:
                if c in known_set:
                    return c
            return candidates[0]

    return None


@st.cache_data(ttl=3600)
def fetch_ibd_stock_of_the_day(known_universe_tuple, max_articles=10):
    """
    Fetch investors.com's IBD Stock Of The Day category page and extract
    tickers from recent article titles. If no direct ticker is present,
    falls back to extracting a company-name phrase and resolving it to a
    ticker via progressive name-trimming across multiple resolvers.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    try:
        resp = requests.get(IBD_STOCK_OF_DAY_URL, headers=headers, timeout=15)
        resp.raise_for_status()
        html = resp.text
    except Exception as e:
        return {"error": f"Fetch error: {e}", "articles": []}

    known_set = set(known_universe_tuple)

    article_pattern = re.compile(
        r'<a[^>]+href="(https://www\.investors\.com/[^"]*ibd-stock-of-the-day[^"]*)"[^>]*>(.*?)</a>',
        re.IGNORECASE | re.DOTALL,
    )

    seen_urls = set()
    articles = []

    for m in article_pattern.finditer(html):
        url = m.group(1)
        raw_title = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        raw_title = re.sub(r"\s+", " ", raw_title)

        if not raw_title or len(raw_title) < 10:
            continue
        if url in seen_urls:
            continue
        seen_urls.add(url)

        tickers = _extract_tickers_from_ibd_sotd_text(raw_title, restrict_to_known=known_set)
        resolved_via = None

        if not tickers:
            name_candidates = _extract_company_name_candidates_from_ibd_title(raw_title)
            url_fallback = _extract_company_name_from_ibd_url(url)
            if url_fallback:
                name_candidates.append(url_fallback)

            for candidate in name_candidates:
                resolved_ticker = _resolve_company_name_to_ticker(candidate, known_universe_tuple)
                if resolved_ticker:
                    tickers = [resolved_ticker]
                    resolved_via = f"name match: '{candidate}'"
                    break

        articles.append({"title": raw_title, "url": url, "tickers": tickers, "resolved_via": resolved_via})

        if len(articles) >= max_articles:
            break

    if not articles:
        page_tickers = _extract_tickers_from_ibd_sotd_text(html, restrict_to_known=known_set)
        if page_tickers:
            return {
                "error": None,
                "articles": [{"title": "(page-wide scan — no article titles matched)",
                              "url": IBD_STOCK_OF_DAY_URL, "tickers": page_tickers, "resolved_via": None}],
            }
        return {"error": "No articles or tickers found — page layout may have changed or request was blocked.",
                "articles": []}

    return {"error": None, "articles": articles}

# ── Render section ────────────────────────────────────────────────────────
#st.markdown("---")
st.write("")
st.markdown(
    "#### 🎓 IBD "
    "<span style='color:#888; font-size:12px;'>(Stock Of The Day)</span>",
    unsafe_allow_html=True,
)

with st.spinner("Fetching IBD Stock Of The Day..."):
    ibd_sotd_result = timed(
        "fetch_ibd_stock_of_the_day",
        fetch_ibd_stock_of_the_day,
        tuple(KNOWN_STOCKS),
    )

if ibd_sotd_result.get("error"):
    st.info(f"Unable to fetch IBD Stock Of The Day — {ibd_sotd_result['error']}")
else:
    all_sotd_tickers = []
    for art in ibd_sotd_result["articles"]:
        all_sotd_tickers.extend(art["tickers"])
    all_sotd_tickers_unique = list(dict.fromkeys(all_sotd_tickers))

    if all_sotd_tickers_unique:
        sotd_industry_counts, sotd_ticker_industry = build_leader_industry_map(all_sotd_tickers_unique, INDUSTRIES)  # NEW
        html_sotd = "<div style='display:flex;flex-wrap:wrap;gap:4px;padding:6px 0;'>"
        for sym in all_sotd_tickers_unique:
            # NEW: top-20 industry glow
            industries = sotd_ticker_industry.get(sym, [])
            ranks = [industry_rank_map[ind] for ind in industries if ind in industry_rank_map]
            is_top20_industry = any(r <= 20 for r in ranks) if ranks else False
            glow_style = (
                "box-shadow:0 0 8px 2px #FF4B4B; border:1px solid #FF4B4B;"
                if is_top20_industry else ""
            )
            html_sotd += setup_badge(sym, is_new=(sym in KNOWN_STOCKS), extra_style=glow_style)  # CHANGED
        html_sotd += "</div>"
        st.markdown(html_sotd, unsafe_allow_html=True)
    else:
        st.info("No tickers extracted from recent articles.")

    st.write("")

    with st.expander(f"Source articles ({len(ibd_sotd_result['articles'])})"):
        for art in ibd_sotd_result["articles"]:
            tick_str = ", ".join(art["tickers"]) if art["tickers"] else "—"
            st.markdown(f"- [{art['title']}]({art['url']}) → **{tick_str}**")

st.markdown("---")

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

with st.spinner("Computing Setup Count history..."):
    setup_count_hist = timed(
        "compute_global_setup_count_history",
        compute_global_setup_count_history,
        stocks_tuple, ticker_dfs_shared
    )

st.markdown(f"#### 📐 Setup Quality")

if not setup_avgrank_hist.empty:
    chart_df_rank = setup_avgrank_hist.merge(setup_count_hist, on="Date", how="left")
    chart_df_rank["Setup Count"] = chart_df_rank["Setup Count"].ffill().fillna(0)
    today_rank = chart_df_rank["Avg Rank"].iloc[-1]
    min_rank = chart_df_rank["Avg Rank"].min()
    min_idx = chart_df_rank["Avg Rank"].idxmin()

    bar_colors = ["#29B5E8"] * len(chart_df_rank)
    bar_colors[chart_df_rank.index.get_loc(min_idx)] = "#90EE90"  # overall lowest bar (best rank)
    if today_rank == min_rank:
        bar_colors[-1] = "#FF4B4B"  # today is also the lowest

    fig_setup = go.Figure()
    fig_setup.add_trace(go.Bar(
        x=chart_df_rank["Date"], y=chart_df_rank["Avg Rank"],
        name="Avg Rank", marker_color=bar_colors, yaxis="y1",
    ))
    fig_setup.add_trace(go.Scatter(
        x=chart_df_rank["Date"], y=chart_df_rank["Setup Count"],
        name="Setup Count", mode="lines", line=dict(color="#FF4B4B", width=2),
        yaxis="y2",
    ))
    fig_setup.update_layout(
        height=320,
        margin=dict(l=20, r=20, t=10, b=20),
        plot_bgcolor="rgba(20,22,30,1)",
        paper_bgcolor="rgba(13,17,23,0)",
        font=dict(color="#cccccc"),
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="center", x=0.5),
        xaxis=dict(showgrid=False, tickfont=dict(size=9, color="#888888")),
        yaxis=dict(title="Avg Rank", showgrid=True, gridcolor="rgba(120,120,120,0.15)", tickfont=dict(color="#888888")),
        yaxis2=dict(title="Setup Count", overlaying="y", side="right", showgrid=False, tickfont=dict(color="#888888")),
    )
    st.plotly_chart(fig_setup, use_container_width=True)
else:
    st.info("Insufficient data to compute Setup Avg Rank history.")

# ==============================================================================
# 13. SEND SETUP SUMMARY TEXT DIRECTLY TO TELEGRAM
# ==============================================================================
def send_telegram_text(text, bot_token, chat_id, parse_mode="HTML"):
    """Send a plain text message to Telegram, chunked under the 4096-char limit."""
    if not text:
        return
    MAX_LEN = 4000  # leave headroom below Telegram's 4096 hard limit

    chunks = []
    current = ""
    for line in text.split("\n"):
        if len(current) + len(line) + 1 > MAX_LEN:
            chunks.append(current)
            current = line
        else:
            current = f"{current}\n{line}" if current else line
    if current:
        chunks.append(current)

    for chunk in chunks:
        try:
            resp = requests.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                data={
                    "chat_id": chat_id,
                    "text": chunk,
                    "parse_mode": parse_mode,
                    "disable_web_page_preview": True,
                },
                timeout=20,
            )
            if resp.status_code != 200:
                print(f"Telegram sendMessage failed: {resp.status_code} {resp.text}")
        except Exception as e:
            print(f"Telegram sendMessage error: {e}")


def build_setup_summary_text(global_setup_tickers, global_setup_ticker_groups,
                               industry_rank_map, all_data,
                               cloud21ema_all, cloudwick_all, ma50bounce_all,
                               ticker_dfs_shared, leader_list=None, nan_ticker_count=0):
    if not global_setup_tickers:
        return None

    leader_set = set(leader_list or [])

    # Global RS lookup
    global_rs_lookup = {}
    for item in all_data:
        for t, s in zip(item["Tickers"]["Ticker"], item["Tickers"]["RS Score"]):
            global_rs_lookup[t] = s

    # Risk %: distance to 21ema-low by default, but distance to SMA50
    # if the ticker's ONLY setup type is 50ma_bounce.
    risk_map = {}
    for sym in global_setup_tickers:
        try:
            df = ticker_dfs_shared.get(sym)
            if df is None or len(df) < 50:
                continue
            close = df['Close']
            low   = df['Low']
            c = close.iloc[-1]

            setup_types_for_risk = []
            if sym in cloud21ema_all: setup_types_for_risk.append("21ema_cloud")
            if sym in cloudwick_all:  setup_types_for_risk.append("21ema_wick")
            if sym in ma50bounce_all: setup_types_for_risk.append("50ma_bounce")

            if setup_types_for_risk == ["50ma_bounce"]:
                sma50 = close.rolling(50).mean().iloc[-1]
                risk_map[sym] = round(float(((c - sma50) / c) * 100), 1)
            else:
                ema21_low = low.ewm(span=21, adjust=False).mean().iloc[-1]
                risk_map[sym] = round(float(((c - ema21_low) / c) * 100), 1)
        except Exception:
            continue

    rows = []
    for sym in global_setup_tickers:
        industries = global_setup_ticker_groups.get(sym, [])
        ranks = [(ind, industry_rank_map[ind]) for ind in industries if ind in industry_rank_map]
        best_industry, best_rank = min(ranks, key=lambda x: x[1]) if ranks else ("-", 9999)

        setup_types = []
        if sym in cloud21ema_all: setup_types.append("21_cloud")
        if sym in cloudwick_all:  setup_types.append("21_wick")
        if sym in ma50bounce_all: setup_types.append("50ma_b")

        rows.append({
            "rank": best_rank,
            "ticker": sym,
            "rs": global_rs_lookup.get(sym, 0),
            "setups": setup_types,
            "risk": risk_map.get(sym),
            "is_leader": sym in leader_set,
        })

    rows.sort(key=lambda r: r["rank"])

    # ── NEW: count how many setups are in a top-20 industry ──
    strong_count = sum(1 for r in rows if r["rank"] <= 20)

    lines = [f"<b>🔥 Setup Summary ({strong_count}/{len(rows)})</b>", ""]
    separator_inserted = False
    for r in rows:
        if not separator_inserted and r["rank"] > 20:
            lines.append("----------")
            separator_inserted = True

        setup_str = ",".join(r["setups"])
        risk_str  = f'{r["risk"]:.1f}%' if r["risk"] is not None else "n/a"
        ticker_str = f'<b><i><u>{r["ticker"]}</u></i></b>' if r["is_leader"] else r["ticker"]
        lines.append(
            f'#{r["rank"]} | {ticker_str} ({r["rs"]:.0f}) | '
            f'{setup_str} | {risk_str}'
        )

    # NEW: last line — NaN-today ticker count
    lines.append("")
    lines.append(f"⚠️ NaN-today: {nan_ticker_count}")

    return "\n".join(lines)

sgt_now = datetime.datetime.now(ZoneInfo("Asia/Singapore"))
in_send_window = (7 <= sgt_now.hour <= 8)  # 17:00–17:59 SGT

today_str = sgt_now.strftime("%Y-%m-%d")
setup_summary_sig = f"{today_str}_{sorted(global_setup_tickers)}"

if in_send_window and st.session_state.get("telegram_setup_summary_sig") != setup_summary_sig:
    summary_text = build_setup_summary_text(
        global_setup_tickers, global_setup_ticker_groups, industry_rank_map,
        all_data, cloud21ema_all, cloudwick_all, ma50bounce_all, ticker_dfs_shared,
        leader_list=leader_list,
        nan_ticker_count=len(_latest_nan_tickers),   # NEW
    )
    tg_token = st.secrets.get("TELEGRAM_BOT_TOKEN")
    tg_chat  = st.secrets.get("TELEGRAM_CHAT_ID")

    if summary_text and tg_token and tg_chat:
        send_telegram_text(summary_text, tg_token, tg_chat)
        st.session_state["telegram_setup_summary_sig"] = setup_summary_sig
    elif not (tg_token and tg_chat):
        st.sidebar.warning("Telegram secrets missing — Setup Summary not sent.")

def massive_get(endpoint, params=None, timeout=15):
    massive_key = st.secrets.get("MASSIVE_API_KEY")
    if not massive_key:
        return None
    params = dict(params or {})
    params["apiKey"] = massive_key
    try:
        r = requests.get(f"https://api.massive.com{endpoint}", params=params, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None
    
def get_stock_news(ticker, limit=3):
    data = massive_get("/v2/reference/news", {"ticker": ticker, "limit": limit})
    return data.get("results", []) if data else []

def get_recent_sec_filings(ticker, limit=3):
    data = massive_get("/v3/reference/sec/filings", {"ticker": ticker, "limit": limit})
    return data.get("results", []) if data else []

def get_form4_insider(ticker, limit=5):
    data = massive_get("/v3/reference/sec/form4", {"ticker": ticker, "limit": limit})
    return data.get("results", []) if data else []

def get_upcoming_earnings_finnhub(ticker, days_ahead=7):
    finnhub_key = st.secrets.get("FINNHUB_API_KEY")
    if not finnhub_key:
        return []

    today = datetime.date.today()
    end = today + datetime.timedelta(days=days_ahead)

    try:
        resp = requests.get(
            "https://finnhub.io/api/v1/calendar/earnings",
            params={
                "from": str(today),
                "to": str(end),
                "symbol": ticker,
                "token": finnhub_key,
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("earningsCalendar", []) or []
    except Exception:
        return []

@st.cache_data(ttl=900)
def fetch_news_for_volatility_hits(tickers_tuple):
    return {t: get_stock_news(t) for t in tickers_tuple}

@st.cache_data(ttl=3600)
def fetch_sec_filings_for_volatility_hits(tickers_tuple):
    return {t: get_recent_sec_filings(t) for t in tickers_tuple}

@st.cache_data(ttl=3600)
def fetch_form4_for_volatility_hits(tickers_tuple):
    return {t: get_form4_insider(t) for t in tickers_tuple}

@st.cache_data(ttl=21600)
def fetch_earnings_for_volatility_hits(tickers_tuple):
    return {t: get_upcoming_earnings_finnhub(t) for t in tickers_tuple}

def explain_volatility_hits(tickers_tuple):
    news_map     = fetch_news_for_volatility_hits(tickers_tuple)
    sec_map      = fetch_sec_filings_for_volatility_hits(tickers_tuple)
    form4_map    = fetch_form4_for_volatility_hits(tickers_tuple)
    earnings_map = fetch_earnings_for_volatility_hits(tickers_tuple)

    reasons = {}
    for t in tickers_tuple:
        tags = []
        if news_map.get(t):
            tags.append("📰 News")
        if any(str(f.get("form_type", "")).upper() == "8-K" for f in sec_map.get(t, [])):
            tags.append("📝 8-K Filed")
        if any("buy" in str(f.get("transaction_type", "")).lower() for f in form4_map.get(t, [])):
            tags.append("👤 Insider Buy")
        # 📅 Earnings Soon tag removed
        reasons[t] = tags

    return reasons, news_map, sec_map, form4_map, earnings_map

# ==============================================================================
# REPLACEMENT FOR: fetch_known_stocks_upcoming_earnings() + its display block
# Drop this in place of the existing "📅 Upcoming Earnings" section.
# ==============================================================================

@st.cache_data(ttl=21600)
def fetch_known_stocks_weekly_earnings(stocks_tuple):
    """
    Fetch KNOWN_STOCKS earnings for the current (or upcoming, if it's the
    weekend) Mon-Fri week from Finnhub.
    Returns (df, monday_date, friday_date). df columns: Ticker, Date, Hour.
    """
    finnhub_key = st.secrets.get("FINNHUB_API_KEY")

    today = datetime.date.today()

    if today.weekday() >= 5:  # Sat=5, Sun=6 → roll to NEXT week's Monday
        days_until_next_monday = 7 - today.weekday()
        monday = today + datetime.timedelta(days=days_until_next_monday)
    else:
        monday = today - datetime.timedelta(days=today.weekday())

    friday = monday + datetime.timedelta(days=4)

    if not finnhub_key:
        return pd.DataFrame(), monday, friday

    known_set = set(stocks_tuple)

    try:
        resp = requests.get(
            "https://finnhub.io/api/v1/calendar/earnings",
            params={"from": str(monday), "to": str(friday), "token": finnhub_key},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        rows = data.get("earningsCalendar", []) or []
    except Exception as e:
        st.warning(f"Finnhub earnings fetch error: {e}")
        return pd.DataFrame(), monday, friday

    filtered = [r for r in rows if r.get("symbol") in known_set]
    if not filtered:
        return pd.DataFrame(), monday, friday

    df = pd.DataFrame([{
        "Ticker": r.get("symbol"),
        "Date": r.get("date"),
        "Hour": r.get("hour"),  # bmo / amc / dmh
    } for r in filtered])

    return df.reset_index(drop=True), monday, friday


@st.cache_data(ttl=21600)
def fetch_market_caps_for_earnings(tickers_tuple):
    """Market cap per ticker (in raw dollars), used to sort the earnings grid largest-first."""
    caps = {}
    for t in tickers_tuple:
        try:
            fi = yf.Ticker(t).fast_info
            cap = fi.get("market_cap") or fi.get("marketCap")
            caps[t] = float(cap) if cap else 0.0
        except Exception:
            caps[t] = 0.0
    return caps


def render_weekly_earnings_grid(df, monday, friday, gold_tickers=None):
    """Render a 5-column (Mon-Fri) x 2-subcolumn (Before Open / After Close) ticker grid."""
    if df is None or df.empty or monday is None:
        st.info("No known-stock earnings this week.")
        return

    if gold_tickers is None:
        gold_tickers = set()

    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    day_dates = [monday + datetime.timedelta(days=i) for i in range(5)]

    # bucket: day_idx -> {"bmo": [...], "amc": [...], "dmh": [...]}
    buckets = {i: {"bmo": [], "amc": [], "dmh": []} for i in range(5)}
    for _, row in df.iterrows():
        try:
            d = datetime.datetime.strptime(row["Date"], "%Y-%m-%d").date()
        except (TypeError, ValueError):
            continue
        if d < monday or d > friday:
            continue
        day_idx = (d - monday).days
        if day_idx < 0 or day_idx > 4:
            continue
        hour = row["Hour"] if row["Hour"] in ("bmo", "amc") else "dmh"
        buckets[day_idx][hour].append(row["Ticker"])

    all_tickers_tuple = tuple(sorted(set(df["Ticker"])))
    market_caps = fetch_market_caps_for_earnings(all_tickers_tuple)

    def ticker_col(tickers):
        if not tickers:
            return "<div style='color:#444;font-size:11px;padding:6px;text-align:center;'>—</div>"
        html = ""
        default_style = "background:#1e1e1e;border:1px solid #444;color:#eeeeee;"
        gold_style = "background:#FFD700;border:1px solid #B8860B;color:#111111;font-weight:bold;"
        sorted_tickers = sorted(set(tickers), key=lambda t: -market_caps.get(t, 0.0))
        for t in sorted_tickers:
            style = gold_style if t in gold_tickers else default_style
            html += (
                f"<div style='margin:2px 0;padding:3px 6px;border-radius:4px;"
                f"font-size:12px;text-align:center;{style}'>{t}</div>"
            )
        return html

    # NOTE: built as flat, non-indented strings — st.markdown treats 4+ leading
    # spaces as a code block, so multi-line indented f-strings render as raw text.
    cols_html = ""
    for i in range(5):
        date_label = day_dates[i].strftime("%b %d")
        bmo_tickers = buckets[i]["bmo"] + buckets[i]["dmh"]  # During-Market folded into Before Open
        amc_tickers = buckets[i]["amc"]

        cols_html += (
            '<td style="vertical-align:top;border-right:2px solid #333;padding:8px;min-width:150px;">'
            f'<div style="text-align:center;font-weight:bold;color:#ffffff;font-size:14px;">{day_names[i]}</div>'
            f'<div style="text-align:center;color:#888888;font-size:11px;margin-bottom:8px;">{date_label}</div>'
            '<table style="width:100%;border-collapse:collapse;"><tr>'
            '<td style="width:50%;vertical-align:top;padding-right:5px;border-right:1px solid #333;">'
            '<div style="text-align:center;font-size:10.5px;color:#4ecdc4;font-weight:bold;margin-bottom:5px;white-space:nowrap;">Before Open</div>'
            f'{ticker_col(bmo_tickers)}'
            '</td>'
            '<td style="width:50%;vertical-align:top;padding-left:5px;">'
            '<div style="text-align:center;font-size:10.5px;color:#FF69B4;font-weight:bold;margin-bottom:5px;white-space:nowrap;">After Close</div>'
            f'{ticker_col(amc_tickers)}'
            '</td>'
            '</tr></table>'
            '</td>'
        )

    grid_html = (
        '<div style="overflow-x:auto;background:#0e1117;border-radius:6px;padding:6px 0;">'
        '<table style="width:100%;border-collapse:collapse;table-layout:fixed;">'
        f'<tr>{cols_html}</tr>'
        '</table>'
        '</div>'
    )
    st.markdown(grid_html, unsafe_allow_html=True)


# ── Display block (replaces the old earnings_df section) ────────────────────
st.markdown("---")

with st.spinner("Fetching upcoming earnings..."):
    weekly_earnings_df, week_monday, week_friday = timed(
        "fetch_known_stocks_weekly_earnings",
        fetch_known_stocks_weekly_earnings,
        stocks_tuple  # your existing tuple(KNOWN_STOCKS)
    )

total_week_count = len(weekly_earnings_df) if weekly_earnings_df is not None and not weekly_earnings_df.empty else 0
week_label = f"{week_monday.strftime('%b %d')} – {week_friday.strftime('%b %d')}" if week_monday else ""
st.markdown(f"#### 📅 Upcoming Earnings = {week_label} ({total_week_count})")

earnings_gold_tickers = set(trending_today) | (
    set(reddit_df_display.head(30)["Ticker"]) if not reddit_df.empty else set()
)
if not st.secrets.get("FINNHUB_API_KEY"):
    st.info("Add FINNHUB_API_KEY to secrets.toml to enable this.")
else:
    render_weekly_earnings_grid(weekly_earnings_df, week_monday, week_friday, gold_tickers=earnings_gold_tickers)

st.markdown("---")
st.markdown("#### 📅 Economic Calendar (This Week)")

@st.cache_data(ttl=3600)  # Refresh hourly to catch new releases
def fetch_economic_calendar():
    url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        
        if not isinstance(data, list):
            return pd.DataFrame()
            
        records = []
        for item in data:
            raw_date = item.get("date", "")
            try:
                dt = datetime.date.fromisoformat(raw_date[:10])
                formatted_date = dt.strftime("%Y-%m-%d (%A)")
            except Exception:
                formatted_date = raw_date[:10]
            
            records.append({
                "date": formatted_date,
                "event": item.get("title", ""),
                "country": item.get("country", ""),
                "previous": item.get("previous", "") or "-",
                "estimate": item.get("forecast", "") or "-",
                "actual": item.get("actual", "") or "-",
                "impact": item.get("impact", "")
            })
            
        return pd.DataFrame(records)
    except Exception as e:
        st.warning(f"Economic calendar fetch error: {e}")
        return pd.DataFrame()

econ_df = fetch_economic_calendar()

ECON_KEYWORDS = [
    "CPI", "PPI", "Nonfarm", "Payroll", "Michigan", "Sentiment",
    "Fed", "FOMC", "Unemployment", "GDP", "Retail Sales", "PMI"
]

if not econ_df.empty and "event" in econ_df.columns:
    mask = econ_df["country"].isin(["USD", "US", "United States"]) & (econ_df["impact"].str.lower() == "high")
    filtered = econ_df[mask].sort_values("date").reset_index(drop=True)

    if filtered.empty:
        st.info("No high-impact US economic events scheduled for this week.")
    else:
        show_cols = [c for c in ["date", "event", "previous", "estimate", "actual", "impact"] if c in filtered.columns]
        display_df = filtered[show_cols]

        # Palette of soft background colors for distinct days (works on dark & light themes)
        DAY_COLORS = [
            "background-color: rgba(59, 130, 246, 0.25)",  # Soft Blue
            "background-color: rgba(16, 185, 129, 0.25)",  # Soft Green
            "background-color: rgba(168, 85, 247, 0.25)",  # Soft Purple
            "background-color: rgba(245, 158, 11, 0.25)",  # Soft Amber
            "background-color: rgba(236, 72, 153, 0.25)",  # Soft Pink
        ]

        # Map each unique date to a color from the palette
        unique_dates = display_df["date"].unique()
        color_map = {date: DAY_COLORS[i % len(DAY_COLORS)] for i, date in enumerate(unique_dates)}

        # Apply row-by-row background styling
        styled_df = display_df.style.apply(
            lambda row: [color_map.get(row["date"], "")] * len(row), 
            axis=1
        )

        st.dataframe(styled_df, use_container_width=True, hide_index=True)
else:
    st.info("Economic calendar data currently unavailable.")

st.markdown("---")
st.markdown("#### 🔎 Volatility Explanation Panel (Massive.com)")

vol_hit_tickers = tuple(sym for sym, z, pct in volatility_hits)

if not st.secrets.get("MASSIVE_API_KEY"):
    st.info("Add MASSIVE_API_KEY to secrets.toml to enable this panel.")
elif not vol_hit_tickers:
    st.info("No volatility hits today.")
else:
    with st.spinner("Fetching news, SEC filings, insider trades & earnings via Massive..."):
        reasons, news_map, sec_map, form4_map, earnings_map = timed(
            "explain_volatility_hits", explain_volatility_hits, vol_hit_tickers
        )

    # Compact badge row (reuses your .ticker-badge CSS)
    badge_html = "<div style='display:flex;flex-wrap:wrap;gap:4px;padding:6px 0;'>"
    for sym in vol_hit_tickers:
        tag_str = " ".join(reasons.get(sym, [])) or "No catalyst"
        badge_html += (
            f'<div class="ticker-badge"><span class="ticker-name">{sym}</span>'
            f'<span class="ticker-rs" style="margin-left:6px;">{tag_str}</span></div>'
        )
    badge_html += "</div>"
    st.markdown(badge_html, unsafe_allow_html=True)

    # Per-ticker detail — only render an expander if a catalyst was actually found
    for sym in vol_hit_tickers:
        news_items = news_map.get(sym, [])
        filings    = sec_map.get(sym, [])
        form4s     = form4_map.get(sym, [])
        #earnings   = earnings_map.get(sym, [])

        if not (news_items or filings or form4s):
            continue

        tag_str = " ".join(reasons.get(sym, [])) or "No catalyst found"
        with st.expander(f"{sym} — {tag_str}"):
            if news_items:
                st.markdown("**📰 News**")
                for n in news_items[:3]:
                    title = n.get("title", "Untitled")
                    url = n.get("article_url") or n.get("url", "")
                    st.markdown(f"- [{title}]({url})" if url else f"- {title}")

            if filings:
                st.markdown("**📝 Recent SEC Filings**")
                for f in filings[:3]:
                    st.markdown(f"- {f.get('form_type','?')} filed {f.get('filing_date','?')}")

            if form4s:
                st.markdown("**👤 Insider Activity (Form 4)**")
                for f in form4s[:5]:
                    st.markdown(
                        f"- {f.get('owner_name','Unknown')}: "
                        f"{f.get('transaction_type','?')} {f.get('shares','?')} shares "
                        f"({f.get('filing_date','?')})"
                    )

            # if earnings:
            #     st.markdown("**📅 Upcoming Earnings**")
            #     for e in earnings[:2]:
            #         when = {"bmo": "Before Open", "amc": "After Close"}.get(e.get("time"), e.get("time", ""))
            #         st.markdown(f"- {e.get('date','?')} ({when})")

# ==============================================================================
# MASTER SETUP CONSOLIDATION TABLE
# Aggregates every tracked screen into one ticker x section table, ticked where
# a ticker currently qualifies for that section, sorted by how many sections
# it appears in (most -> least). Also flags whether ANY industry the ticker
# belongs to is currently in the top 20 by Group RS.
# ==============================================================================
st.markdown("---")

# Global "21ema_valid" set = the underlying buyable/cloud-eligible list
# (item["Cloud"] per industry), same pool that feeds 21ema_cloud/wick/50ma_bounce.
cloud_valid_all = set()
for item in all_data:
    cloud_valid_all.update(item.get("Cloud", []))

# Column label -> set of tickers currently qualifying for that section.
# Built defensively: several of these (pt_syms, coc_today, etc.) only get
# defined inside their section's "if list or yest_list:" conditional block,
# so on a day where that list is empty the variable never exists. Reading
# everything through globals().get(...) with a safe default avoids a
# NameError crash on those quiet days.
_pt_list_safe = globals().get("pt_list", [])
_pt_syms_fallback = set(
    item[0] if isinstance(item, tuple) else item for item in _pt_list_safe
)

SECTION_DEFINITIONS = {
    "Minervini":          set(sym for sym, _, _ in globals().get("email_content_stocks", [])),
    "RS Leader":          set(globals().get("leader_list", [])),
    "TML":                set(globals().get("tml_list", [])),
    "PPP":                set(globals().get("ppp_list", [])),    
    "RS NH B4 Price":     set(globals().get("rs_nh_b4_today", [])),
    "Gapper":             set(globals().get("gapper_list", [])),          # short form
    "Early Bull":         set(globals().get("early_bull_list", [])),
    "Two Botak":          set(globals().get("b_list", [])),
    "Engulfing":          set(globals().get("engulf_combined_syms", [])),
    "PowerTrend":         _pt_syms_fallback,
    "CoC":                set(globals().get("coc_today", [])),            # short form
    "21ema_valid":        cloud_valid_all,
    "21ema_cloud":        cloud21ema_all,
    "21ema_wick":         cloudwick_all,
    "50ma_bounce":        ma50bounce_all,
}

# Reverse lookup: ticker -> industries it belongs to (built once, O(1) lookups after)
ticker_to_industries = {}
for _industry, _tickers_in_group in INDUSTRIES.items():
    for _t in _tickers_in_group:
        ticker_to_industries.setdefault(_t, []).append(_industry)

def _ticker_is_top20_industry(sym):
    """True if ANY industry this ticker belongs to is currently ranked <= 20 by Group RS."""
    return any(
        industry_rank_map.get(ind, 9999) <= 20
        for ind in ticker_to_industries.get(sym, [])
    )

# ── Extra non-counted columns (not part of SECTION_DEFINITIONS/Count) ──────
# Volatility: ticker itself hit today's volatility Z-score screen
_vol_hits_safe = globals().get("volatility_hits", [])
vol_hit_syms = set(sym for sym, _z, _pct in _vol_hits_safe)
_lime_stocks1_safe = set(globals().get("LIME_STOCKS1", []))

# Distribution: ticker belongs to an industry currently flagged for
# distribution (the same set that colors the industry-table rank number red)
_vol_flagged_industries_safe = globals().get("vol_flagged_industries", set())

def _ticker_in_distribution_industry(sym):
    return any(
        ind in _vol_flagged_industries_safe
        for ind in ticker_to_industries.get(sym, [])
    )

# Union of every ticker appearing in at least one counted section,
# restricted to the KNOWN_STOCKS universe only.
master_ticker_set = set()
for _tset in SECTION_DEFINITIONS.values():
    master_ticker_set.update(_tset)
master_ticker_set &= set(KNOWN_STOCKS)

master_rows = []
for sym in master_ticker_set:
    section_flags = {label: (sym in tset) for label, tset in SECTION_DEFINITIONS.items()}
    is_top20 = _ticker_is_top20_industry(sym)
    master_rows.append({
        "Ticker": sym,
        "Count": sum(section_flags.values()) + (1 if is_top20 else 0),
        "Top20 Industry": is_top20,
        "Volatility": sym in vol_hit_syms,
        "Distribution": _ticker_in_distribution_industry(sym),
        **section_flags,
    })

# Most sections first, then alphabetical tiebreaker
master_rows.sort(key=lambda r: (-r["Count"], r["Ticker"]))
st.markdown(f"#### 📋 Lazy Table ({len(master_rows)})")

if master_rows:
    section_cols = list(SECTION_DEFINITIONS.keys())
    extra_cols = ["Volatility", "Distribution"]  # appended at the very end, not counted

    # Columns that should get a divider line on their RIGHT edge,
    # marking the end of a logical group. No horizontal lines added.
    GROUP_DIVIDER_AFTER = {
        "TML",                 # ends: Minervini / RS Leader / True Market Leader
        "Early Bull",          # ends: RS NH B4 Price -> Early Bull
        "CoC",                 # ends: Two Botak -> CoC
        "50ma_bounce",         # ends: 21ema_valid -> 50ma_bounce
    }
    # box-shadow instead of border-right: it paints directly on the cell and
    # is never subject to the table's border-collapse conflict resolution,
    # so it can't be swallowed by the leaked nth-child(7) red border rule.
    DIVIDER_STYLE = "box-shadow: inset -3px 0 0 0 #ffffff;"
    TML_DIVIDER_STYLE = "box-shadow: inset -3px 0 0 0 #ff0000;"
    THICK_DIVIDER_STYLE = "box-shadow: inset -3px 0 0 0 #ffffff;"  # NEW: Count | Industry separator

    rows_html = ""
    for row_num, row in enumerate(master_rows, start=1):
        bg = "#262730" if row_num % 2 == 0 else "#0e1117"
        ticker_color = "#FF4B4B" if (row["Volatility"] or row["Distribution"]) else ("#00FF00" if row["Ticker"] in _lime_stocks1_safe else "#ffffff")
        no_ema_setup = not (row["21ema_valid"] or row["21ema_cloud"] or row["21ema_wick"] or row["50ma_bounce"])  # NEW
        ticker_style = f"font-weight:bold;color:{ticker_color};white-space:nowrap;" + ("text-decoration:line-through;" if no_ema_setup else "")  # NEW
        top20_mark = (
            "<span style='color:#FFD700;font-weight:bold;'>★</span>"
            if row["Top20 Industry"] else ""
        )
        section_cells = "".join(
            f"<td style='text-align:center;{TML_DIVIDER_STYLE if col == 'TML' else DIVIDER_STYLE if col in GROUP_DIVIDER_AFTER else ''}'>"
            f"{'<span style=\"color:#00FF00;font-weight:bold;\">✔</span>' if row[col] else ''}"
            f"</td>"
            for col in section_cols
        )
        extra_cells = "".join(
            f"<td style='text-align:center;'>"
            f"{'<span style=\"color:#FF4B4B;font-weight:bold;\">✗</span>' if row[col] else ''}"
            f"</td>"
            for col in extra_cols
        )
        rows_html += (
            f"<tr style='background-color:{bg};'>"
            f"<td style='text-align:center;color:#888888;'>{row_num}</td>"
            f"<td style='{ticker_style}'>{row['Ticker']}</td>"  # CHANGED: inline style -> {ticker_style}
            f"<td style='text-align:center;color:#4ecdc4;font-weight:bold;{THICK_DIVIDER_STYLE}'>{row['Count']}</td>"
            f"<td style='text-align:center;'>{top20_mark}</td>"
            f"{section_cells}{extra_cells}</tr>"
        )

    header_cells = "".join(
        f"<th style='text-align:center;font-size:11px;white-space:nowrap;padding:4px 6px;"
        f"{TML_DIVIDER_STYLE if col == 'TML' else DIVIDER_STYLE if col in GROUP_DIVIDER_AFTER else ''}'>{col}</th>"
        for col in section_cols
    )
    extra_header_cells = "".join(
        f"<th style='text-align:center;font-size:11px;white-space:nowrap;padding:4px 6px;'>{col}</th>"
        for col in extra_cols
    )

    master_table_html = f"""
    <style>
    .master-setup-table tbody tr:nth-child(21) td {{
        border-top: none !important;
    }}
    .master-setup-table th:nth-child(3), .master-setup-table td:nth-child(3),
    .master-setup-table th:nth-child(6), .master-setup-table td:nth-child(6),
    .master-setup-table th:nth-child(7), .master-setup-table td:nth-child(7) {{
        border-right: none !important;
    }}
    </style>
    <div class="master-setup-table" style="overflow-x:auto; background:#0e1117; border-radius:6px;">
    <table style="width:100%; border-collapse:collapse;">
    <thead><tr>
    <th style="width:30px; text-align:center;">#</th>
    <th style="text-align:center;">Ticker</th>
    <th style="width:55px; text-align:center;{THICK_DIVIDER_STYLE}">Count</th>
    <th style="width:70px; text-align:center;">Industry</th>
    {header_cells}
    {extra_header_cells}
    </tr></thead>
    <tbody>{rows_html}</tbody>
    </table>
    </div>
    """
    st.markdown(master_table_html, unsafe_allow_html=True)
else:
    st.info("No tickers currently qualify for any tracked setup.")

# ==============================================================================
# 14. ALL-CHARTS COMPARISON GRID — read-only, appended at the very bottom.
# Vertical stack, narrow height, each chart keeps its ORIGINAL coloring logic
# (z-score outliers, today's max/min highlight, etc.) so they match the
# individually-rendered versions earlier in the script. Category x-axis on
# every chart = no weekend/gap spacing, bars sit flush, dates line up
# across charts for easy comparison.
# ==============================================================================
# st.markdown("---")
# st.markdown("#### 📊 All Charts — Side-by-Side Comparison")

# _compare_days = st.slider(
#     "Days to display", min_value=10, max_value=60, value=60, step=5,
#     key="compare_grid_days"
# )

st.markdown("---")
st.markdown("#### 📊 Lazy Charts")

_compare_days = 60

# ── Shared color helpers, mirroring each chart's original logic exactly ────
def _zscore_outlier_colors(values, base="#29B5E8", outlier="#FF4B4B",
                            check_max=True, check_min=False,
                            max_color=None, min_color=None, z_check=True):
    vals = pd.Series(values).astype(float)
    colors = [base] * len(vals)
    if z_check and len(vals) > 1:
        mean_v, std_v = vals.mean(), vals.std(ddof=1)
        if std_v and std_v > 0:
            z = (vals - mean_v) / std_v
            for i, zi in enumerate(z):
                if zi >= 2:
                    colors[i] = outlier
    if len(vals) > 0:
        today_val = vals.iloc[-1]
        mx, mn = vals.max(), vals.min()
        mcolor = max_color or outlier
        mncolor = min_color or outlier
        if check_min and today_val == mn:
            colors[-1] = mncolor
        elif check_max and today_val == mx:
            colors[-1] = mcolor
    return colors


def _max_only_colors(values, base="#29B5E8", outlier="#FF4B4B"):
    """No z-score check — only today's-bar-is-max gets highlighted (Engulfing style)."""
    vals = pd.Series(values).astype(float)
    colors = [base] * len(vals)
    if len(vals) > 0 and vals.iloc[-1] == vals.max():
        colors[-1] = outlier
    return colors


def _render_bar_chart(title, df, date_col, value_col, colors, height=110, days=30):
    if df is None or not isinstance(df, pd.DataFrame) or df.empty or date_col not in df.columns:
        st.caption(f"**{title}** — no data")
        return
    plot_df = df.tail(days).reset_index(drop=True)
    plot_colors = colors[-len(plot_df):] if colors else ["#29B5E8"] * len(plot_df)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=plot_df[date_col].astype(str), y=plot_df[value_col],
        marker_color=plot_colors, showlegend=False,
    ))
    fig.update_layout(
        title=dict(text=title, font=dict(size=11, color="#cccccc"), x=0.01, y=0.95),
        height=height,
        margin=dict(l=4, r=4, t=24, b=18),
        plot_bgcolor="rgba(20,22,30,1)",
        paper_bgcolor="rgba(13,17,23,0)",
        bargap=0,  # flush bars, no gaps
        xaxis=dict(type="category", showgrid=False, tickfont=dict(size=7, color="#666666"), nticks=6),
        yaxis=dict(showgrid=True, gridcolor="rgba(120,120,120,0.12)", tickfont=dict(size=8, color="#666666")),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def _render_multi_line_chart(title, df, date_col, series, height=110, days=30, show_legend=True):
    if df is None or not isinstance(df, pd.DataFrame) or df.empty or date_col not in df.columns:
        st.caption(f"**{title}** — no data")
        return
    plot_df = df.tail(days).reset_index(drop=True)

    fig = go.Figure()
    for col, color in series:
        if col not in plot_df.columns:
            continue
        fig.add_trace(go.Scatter(
            x=plot_df[date_col].astype(str), y=plot_df[col],
            mode="lines", name=col, line=dict(color=color, width=1.6),
            showlegend=show_legend,
        ))
    fig.update_layout(
        title=dict(text=title, font=dict(size=11, color="#cccccc"), x=0.01, y=0.95),
        height=height,
        margin=dict(l=4, r=4, t=24, b=18),
        plot_bgcolor="rgba(20,22,30,1)",
        paper_bgcolor="rgba(13,17,23,0)",
        xaxis=dict(type="category", showgrid=False, tickfont=dict(size=7, color="#666666"), nticks=6),
        yaxis=dict(showgrid=True, gridcolor="rgba(120,120,120,0.12)", tickfont=dict(size=8, color="#666666")),
        legend=dict(font=dict(size=8), orientation="h", yanchor="bottom", y=1.0, x=0.01),
        showlegend=show_legend,
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def _render_two_bar_chart(title, df, date_col, value_col, colors_a,
                           value_col2, colors_b, height=110, days=30):
    """Two side-by-side single-series bar charts, e.g. Biggest Up / Biggest Down."""
    if df is None or not isinstance(df, pd.DataFrame) or df.empty or date_col not in df.columns:
        st.caption(f"**{title}** — no data")
        return
    c1, c2 = st.columns(2)
    with c1:
        _render_bar_chart(f"{title} (Up)", df, date_col, value_col, colors_a, height=height, days=days)
    with c2:
        _render_bar_chart(f"{title} (Down)", df, date_col, value_col2, colors_b, height=height, days=days)


_NARROW_HEIGHT = 110

# ── 1. Minervini Count (line, matches original color logic) ────────────────
if isinstance(globals().get("historical_df", None), pd.DataFrame) and not historical_df.empty:
    _chart_df_min = historical_df.copy()
    _chart_df_min["20D MA"] = _chart_df_min["Minervini Count"].rolling(window=20, min_periods=1).mean().round(1)
    _ma_color = globals().get("status_color", "#FF4B4B")
    _render_multi_line_chart(
        "Mark Minervini", _chart_df_min, "Date",
        [("Minervini Count", "#1f77b4"), ("20D MA", _ma_color)],
        height=_NARROW_HEIGHT, days=_compare_days,
        show_legend=False
    )
else:
    st.caption("**Minervini Count** — no data")

# ── 2. RS Leader Count (z-score + max/min highlight) ────────────────────────
if isinstance(globals().get("leader_hist", None), pd.DataFrame) and not leader_hist.empty:
    _colors = _zscore_outlier_colors(leader_hist["Leader Count"], check_max=True, check_min=True)
    _render_bar_chart("RS Leader = Long term", leader_hist, "Date", "Leader Count", _colors, height=_NARROW_HEIGHT, days=_compare_days)
else:
    st.caption("**RS Leader Count** — no data")

# ── 11. True Market Leader (z-score + gold-max/red-min, matches original) ──
if isinstance(globals().get("tml_hist", None), pd.DataFrame) and not tml_hist.empty:
    _colors = _zscore_outlier_colors(
        tml_hist["TML Count"], check_max=True, check_min=True,
        max_color="#FFD700", min_color="#FF4B4B"
    )
    _render_bar_chart("True Market Leader = A+ Leader on weakness is a gift", tml_hist, "Date", "TML Count", _colors, height=_NARROW_HEIGHT, days=_compare_days)
else:
    st.caption("**True Market Leader Count** — no data")

st.markdown("---")

# ── 13. Change of Character (z-score + max-only highlight) ──────────────────
if isinstance(globals().get("coc_hist", None), pd.DataFrame) and not coc_hist.empty:
    _colors = _zscore_outlier_colors(coc_hist["CoC Count"], check_max=True, check_min=False)
    _render_bar_chart("Change of Character", coc_hist, "Date", "CoC Count", _colors, height=_NARROW_HEIGHT, days=_compare_days)
else:
    st.caption("**Change of Character Count** — no data")

# ── Biggest Up Count ─────────────────────────────────────────────────────
if isinstance(globals().get("biggest_move_hist", None), pd.DataFrame) and not biggest_move_hist.empty:
    _colors_up = _zscore_outlier_colors(biggest_move_hist["Biggest Up Count"], check_max=True, check_min=False)
    _render_bar_chart("Biggest Up", biggest_move_hist, "Date", "Biggest Up Count", _colors_up, height=_NARROW_HEIGHT, days=_compare_days)
else:
    st.caption("**Biggest Up Count** — no data")

st.markdown("---")


# ── 14. Breakdown of Character (z-score + max-only highlight) ───────────────
if isinstance(globals().get("boc_hist", None), pd.DataFrame) and not boc_hist.empty:
    _colors = _zscore_outlier_colors(boc_hist["BoC Count"], check_max=True, check_min=False)
    _render_bar_chart("Breakdown of Character", boc_hist, "Date", "BoC Count", _colors, height=_NARROW_HEIGHT, days=_compare_days)
else:
    st.caption("**Breakdown of Character Count** — no data")

# ── Biggest Down Count ───────────────────────────────────────────────────
if isinstance(globals().get("biggest_move_hist", None), pd.DataFrame) and not biggest_move_hist.empty:
    _colors_down = _zscore_outlier_colors(biggest_move_hist["Biggest Down Count"], check_max=True, check_min=False)
    _render_bar_chart("Biggest Down", biggest_move_hist, "Date", "Biggest Down Count", _colors_down, height=_NARROW_HEIGHT, days=_compare_days)
else:
    st.caption("**Biggest Down Count** — no data")

# ── 9. Volatility (z-score + max-only highlight) ────────────────────────────
if isinstance(globals().get("volatility_hist", None), pd.DataFrame) and not volatility_hist.empty:
    _colors = _zscore_outlier_colors(volatility_hist["Volatility Count"], check_max=True, check_min=False)
    _render_bar_chart("Volatility", volatility_hist, "Date", "Volatility Count", _colors, height=_NARROW_HEIGHT, days=_compare_days)
else:
    st.caption("**Volatility Count** — no data")

# ── 8. Value Trap (z-score + max-only highlight) ────────────────────────────
if isinstance(globals().get("value_trap_hist", None), pd.DataFrame) and not value_trap_hist.empty:
    _colors = _zscore_outlier_colors(value_trap_hist["Value Trap Count"], check_max=True, check_min=False)
    _render_bar_chart("Value Trap = MAG7 & MOAT", value_trap_hist, "Date", "Value Trap Count", _colors, height=_NARROW_HEIGHT, days=_compare_days)
else:
    st.caption("**Value Trap Count** — no data")

st.markdown("---")

# ── 3. Stage 2 vs Stage 4 (line, no bar coloring in original) ──────────────
if isinstance(globals().get("stage_hist", None), pd.DataFrame) and not stage_hist.empty:
    _render_multi_line_chart(
        "Stage 2 vs Stage 4", stage_hist, "Date",
        [("S2 Count", "#378ADD"), ("S4 Count", "#FF69B4")],
        height=_NARROW_HEIGHT, days=_compare_days,
        show_legend=False
    )
else:
    st.caption("**Stage 2 vs Stage 4** — no data")

# ── 10. Gapper (z-score + max/min highlight) ────────────────────────────────
if isinstance(globals().get("gapper_hist", None), pd.DataFrame) and not gapper_hist.empty:
    _colors = _zscore_outlier_colors(gapper_hist["Gapper Count"], check_max=True, check_min=True)
    _render_bar_chart("Gapper = Earning Season Drift", gapper_hist, "Date", "Gapper Count", _colors, height=_NARROW_HEIGHT, days=_compare_days)
else:
    st.caption("**Gapper Count** — no data")

# ── 12. Early Bull (z-score + max-only highlight) ───────────────────────────
if isinstance(globals().get("early_bull_hist", None), pd.DataFrame) and not early_bull_hist.empty:
    _colors = _zscore_outlier_colors(early_bull_hist["Early Bull Count"], check_max=True, check_min=False)
    _render_bar_chart("Early Bull = Stage 1 -> 2", early_bull_hist, "Date", "Early Bull Count", _colors, height=_NARROW_HEIGHT, days=_compare_days)
else:
    st.caption("**Early Bull Count** — no data")

# ── 4. Two Botak (z-score + max-only highlight) ─────────────────────────────
if isinstance(globals().get("two_botak_hist", None), pd.DataFrame) and not two_botak_hist.empty:
    _colors = _zscore_outlier_colors(two_botak_hist["Two Botak Count"], check_max=True, check_min=False)
    _render_bar_chart("Two Botak = Short term Group burst", two_botak_hist, "Date", "Two Botak Count", _colors, height=_NARROW_HEIGHT, days=_compare_days)
else:
    st.caption("**Two Botak Count** — no data")

# ── 5/6. 2x / 3x Engulfing (max-only, no z-score, matches original) ────────
if isinstance(globals().get("engulf_hist", None), pd.DataFrame) and not engulf_hist.empty:
    _colors_2x = _max_only_colors(engulf_hist["2x Engulfing Count"])
    _render_bar_chart("2x Engulfing = HL", engulf_hist, "Date", "2x Engulfing Count", _colors_2x, height=_NARROW_HEIGHT, days=_compare_days)
    _colors_3x = _max_only_colors(engulf_hist["3x Engulfing Count"])
    _render_bar_chart("3x Engulfing = HL", engulf_hist, "Date", "3x Engulfing Count", _colors_3x, height=_NARROW_HEIGHT, days=_compare_days)
else:
    st.caption("**2x/3x Engulfing Count** — no data")

# ── 7. PowerTrend (z-score + max/min highlight) ─────────────────────────────
if isinstance(globals().get("powertrend_hist", None), pd.DataFrame) and not powertrend_hist.empty:
    _colors = _zscore_outlier_colors(powertrend_hist["PowerTrend Count"], check_max=True, check_min=True)
    _render_bar_chart("PowerTrend = Thematic Extended", powertrend_hist, "Date", "PowerTrend Count", _colors, height=_NARROW_HEIGHT, days=_compare_days)
else:
    st.caption("**PowerTrend Count** — no data")

# ── 16. Setup Avg Rank (bespoke: lime=overall best, red=today-if-best) ─────
# This is the one that needed the gap fix — category x-axis + bargap=0 below
# makes it render flush like every other chart in this grid.
_setup_avgrank_hist = globals().get("setup_avgrank_hist", None)
_setup_count_hist = globals().get("setup_count_hist", None)
if isinstance(_setup_avgrank_hist, pd.DataFrame) and not _setup_avgrank_hist.empty:
    _chart_df_rank = _setup_avgrank_hist.tail(_compare_days).reset_index(drop=True)
    if isinstance(_setup_count_hist, pd.DataFrame) and not _setup_count_hist.empty:
        _chart_df_rank = _chart_df_rank.merge(_setup_count_hist, on="Date", how="left")
        _chart_df_rank["Setup Count"] = _chart_df_rank["Setup Count"].ffill().fillna(0)
    else:
        _chart_df_rank["Setup Count"] = 0

    _today_rank = _chart_df_rank["Avg Rank"].iloc[-1]
    _min_rank = _chart_df_rank["Avg Rank"].min()
    _min_idx = _chart_df_rank["Avg Rank"].idxmin()

    _bar_colors = ["#29B5E8"] * len(_chart_df_rank)
    _bar_colors[_chart_df_rank.index.get_loc(_min_idx)] = "#90EE90"
    if _today_rank == _min_rank:
        _bar_colors[-1] = "#FF4B4B"

    _fig_setup = go.Figure()
    _fig_setup.add_trace(go.Bar(
        x=_chart_df_rank["Date"].astype(str), y=_chart_df_rank["Avg Rank"],
        name="Avg Rank", marker_color=_bar_colors, yaxis="y1",
    ))
    _fig_setup.add_trace(go.Scatter(
        x=_chart_df_rank["Date"].astype(str), y=_chart_df_rank["Setup Count"],
        name="Setup Count", mode="lines", line=dict(color="#FF4B4B", width=1.6),
        yaxis="y2",
    ))
    _fig_setup.update_layout(
        title=dict(text="Setup Avg Rank", font=dict(size=11, color="#cccccc"), x=0.01, y=0.95),
        height=_NARROW_HEIGHT,
        margin=dict(l=4, r=4, t=24, b=18),
        plot_bgcolor="rgba(20,22,30,1)",
        paper_bgcolor="rgba(13,17,23,0)",
        bargap=0,  # ← fixes the weekly-gap issue: bars now flush like every other chart
        xaxis=dict(type="category", showgrid=False, tickfont=dict(size=7, color="#666666"), nticks=6),
        #yaxis=dict(title="Rank", showgrid=True, gridcolor="rgba(120,120,120,0.12)", tickfont=dict(size=8, color="#666666")),
        #yaxis2=dict(title="Setup", overlaying="y", side="right", showgrid=False, tickfont=dict(size=8, color="#666666")),
        yaxis=dict(showgrid=True, gridcolor="rgba(120,120,120,0.12)", tickfont=dict(size=8, color="#666666")),
        yaxis2=dict(overlaying="y", side="right", showgrid=False, tickfont=dict(size=8, color="#666666")),
        legend=dict(font=dict(size=8), orientation="h", yanchor="bottom", y=1.0, x=0.01),
        showlegend=False,
    )
    st.plotly_chart(_fig_setup, use_container_width=True, config={"displayModeBar": False})
else:
    st.caption("**Setup Avg Rank** — no data")

