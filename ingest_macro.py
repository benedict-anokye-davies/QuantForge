import pandas as pd

import pandas_datareader.data as web

import yfinance as yf

import datetime



def ingest_macro_data():

    print("Starting Data Fusion (Price + Macro + Sentiment)...")



    start_date = '2015-01-01'

    end_date = datetime.datetime.today().strftime('%Y-%m-%d')





    print(f"Fetching SPY data ({start_date} to {end_date})...")

    spy = yf.download('SPY', start=start_date, end=end_date)



    if isinstance(spy.columns, pd.MultiIndex):

        spy.columns = spy.columns.get_level_values(0)



    spy = spy[['Close', 'Volume']]

    spy.rename(columns={'Close': 'SPY_Close', 'Volume': 'SPY_Volume'}, inplace=True)





    print("Fetching Macro Data (Fed Funds, Yield Curve)...")







    try:

        macro_tickers = ['FEDFUNDS', 'T10Y2Y', 'DGS10']

        macro = web.DataReader(macro_tickers, 'fred', start_date, end_date)

        macro.rename(columns={

            'FEDFUNDS': 'Fed_Rate',

            'T10Y2Y': 'Yield_Curve',

            'DGS10': '10Y_Yield'

        }, inplace=True)

    except Exception as e:

        print(f"Error fetching FRED data: {e}")

        return





    print("Fetching Sentiment Data (VIX, Credit Spreads)...")





    sentiment_tickers = ['^VIX', 'HYG']

    sentiment = yf.download(sentiment_tickers, start=start_date, end=end_date)['Close']





    if isinstance(sentiment.columns, pd.MultiIndex):

        sentiment.columns = sentiment.columns.get_level_values(0)





        pass



    sentiment.rename(columns={'^VIX': 'VIX', 'HYG': 'Junk_Bonds'}, inplace=True)





    print("Merging datasets...")



    df = spy.join(macro, how='left')

    df = df.join(sentiment, how='left')







    df.ffill(inplace=True)





    df.dropna(inplace=True)











    df['Credit_Risk'] = df['SPY_Close'] / df['Junk_Bonds']





    df['Real_Rates'] = df['10Y_Yield'] - df['Fed_Rate']





    df['VIX_Stress'] = df['VIX'] / df['VIX'].rolling(50).mean()





    df['Inverted_Curve'] = (df['Yield_Curve'] < 0).astype(int)





    output_path = 'quantforge/data/csv/SPY_FULL_FEATURES.csv'

    df.to_csv(output_path)

    print(f"Data Fusion Complete. Saved to {output_path}")

    print(f"Shape: {df.shape}")

    print("Sample:\n", df.tail())



if __name__ == "__main__":

    ingest_macro_data()
