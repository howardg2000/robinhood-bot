import pandas as pd
import robin_stocks.robinhood as rh
import datetime as dt
import pytz
from time import sleep

from config import RH_USERNAME, RH_PASSWORD 

class RobinHoodBot:
    def __init__(self, username, password, watchlist=None, stocks=None, strategy=None) -> None:
        """
        Args:
            username (str): robinhood username
            password (str): robinhood password
            watchlist (str): name of existing stock watchlist on robinhood to trade on
            stocks (list[str]): list of stock symbols to trade on, priority given to watchlist
            strategy (function): a function which takes symbols as input and outputs a trade (TODO)
        """

        self._login(username, password)

        self.stocks = stocks
        if self.stocks is None:
            self.stocks = []
        if watchlist is not None:
            self.stocks = self.get_watchlist(watchlist)

        self.open_orders = self.get_all_open_stock_orders()

        self.get_portfolio()

    def _login(self, username, password):
        rh.authentication.login(username, password)

    def logout(self):
        rh.authentication.logout()

    def get_portfolio(self):
        """
        Get symbols in portfolio. Used to determine if we can sell a position. 
        """

        holdings = rh.build_holdings()
        stock_data = rh.get_open_stock_positions()
        for stock in stock_data:
            stock_info = rh.get_instrument_by_url(stock['instrument'])
            symbol = stock_info['symbol']
            if symbol in holdings:
                buy_time = pd.to_datetime(stock['created_at']).tz_convert('US/Eastern')
                holdings[symbol]['created_at'] = buy_time
        self.portfolio = holdings
        self.portfolio_symbols = list(holdings.keys())
        return holdings

        # for option in options_data:
        #     info = rh.get_option_instrument_data_by_id(option['option_id'])
        #     option['average_price']
        #     print(info)
        #     strike_price
        #     chain_symbol
    
    def get_watchlist(self, watchlist):
        """Get list of symbols from robinhood watchlist. """
        stockList = rh.get_watchlist_by_name(name=watchlist)
        return [stock['symbol'] for stock in stockList['results']]

    def buy_stock(self, symbol, order_type, price=None, quantity=None, dollar_amount=None):
        """Submit a buy order
        Args:
            symbol (str): stock symbol
            order_type (str): one of fractional_price, fractional_quantity, limit, market
            price (int): desired trade price, only required for limit orders
            quantity (float/int): desired trade quantity, required for fractional_quantity, limit, market orders
            dollar_amount (float): desired total trade notional amount, required for fractional_quantity

        Returns:
            buy_order (dict): robinhood object with details of order
        """
        if order_type == 'fractional_price':
            if dollar_amount is None:
                raise ValueError("No dollar amount specified.")
            if dollar_amount < 0:
                raise ValueError("Negative dollar amount.")
            buy_order = rh.orders.order_buy_fractional_by_price(symbol, dollar_amount)
        elif order_type == 'fractional_quantity':
            if quantity is None:
                raise ValueError("No quantity specified.")
            if quantity < 0:
                raise ValueError("Negative quantity.")
            buy_order = rh.orders.order_buy_fractional_by_quantity(symbol, quantity)
        elif order_type == 'limit':
            if price is None or quantity is None:
                raise ValueError("No price or quantity specified.")
            if quantity < 0 or price < 0:
                raise ValueError("Negative quantity or price.")
            buy_order = rh.orders.order_buy_limit(symbol, int(quantity), price)
        elif order_type == 'market':
            if quantity is None:
                raise ValueError("No quantity specified.")
            if quantity < 0:
                raise ValueError("Negative quantity.")
            buy_order = rh.orders.order_buy_market(symbol, int(quantity))
        # elif order_type == 'stop_limit':
        #     buy_order = rh.orders.order_buy_stop_limit(symbol, price)
        else:
            raise ValueError("Unsupported buy order type: ", order_type)
        print(f"BUY ORDER SUBMITTED {symbol} {order_type}")
        buy_order['symbol'] = symbol
        if 'id' not in buy_order:
            print("FAILED ORDER", buy_order)
        else:
            self.open_orders[buy_order['id']] = buy_order
        return buy_order

    def sell_stock(self, symbol, order_type, price=None, quantity=None, dollar_amount=None):
        """Submit a sell order
        Args:
            symbol (str): stock symbol
            order_type (str): one of fractional_price, fractional_quantity, limit, market
            price (int): desired trade price, only required for limit orders
            quantity (float/int): desired trade quantity, required for fractional_quantity, limit, market orders
            dollar_amount (float): desired total trade notional amount, required for fractional_quantity

        Returns:
            sell_order (dict): robinhood object with details of order
        """
        if order_type == 'fractional_price':
            if dollar_amount is None:
                raise ValueError("No dollar amount specified")
            if dollar_amount < 0:
                raise ValueError("Negative dollar amount.")
            sell_order = rh.orders.order_sell_fractional_by_price(symbol, dollar_amount)
        elif order_type == 'fractional_quantity':
            if quantity is None:
                raise ValueError("No quantity specified")
            if quantity < 0:
                raise ValueError("Negative quantity.")
            sell_order = rh.orders.order_sell_fractional_by_quantity(symbol, quantity)
        elif order_type == 'limit':
            if price is None or quantity is None:
                raise ValueError("No price or quantity specified")
            if quantity < 0 or price < 0:
                raise ValueError("Negative quantity or price.")
            sell_order = rh.orders.order_sell_limit(symbol, int(quantity), price)
        elif order_type == 'market':
            if quantity is None:
                raise ValueError("No quantity specified")
            if quantity < 0:
                raise ValueError("Negative quantity.")
            sell_order = rh.orders.order_sell_market(symbol, int(quantity))
        else:
            raise ValueError("Unsupported buy order type: ", order_type)
        sell_order['symbol'] = symbol
        if 'id' not in sell_order:
            print("FAILED ORDER", sell_order)
        else:
            self.open_orders[sell_order['id']] = sell_order
        print(f"SELL ORDER SUBMITTED {symbol} {order_type}")
        return sell_order

    def cancel_stock_order(self, orderID):
        status = rh.orders.cancel_stock_order(orderID)
        return status

    def cancel_all_stock_orders(self):
        orders = rh.orders.cancel_all_stock_orders()
        return orders

    def get_all_open_stock_orders(self):
        orders = rh.orders.get_all_open_stock_orders()
        order_dict = {}
        for order in orders:
            stock_info = rh.get_instrument_by_url(order['instrument'])
            symbol = stock_info['symbol']
            order['symbol'] = symbol
            order_dict[order['id']] = order
        return order_dict
    
    def update_open_orders(self):
        remove_orders = []
        for order_id in self.open_orders:
            order_info = rh.get_stock_order_info(order_id)
            print(order_info)
            if order_info['state'] == 'filled' or order_info['state'] == 'cancelled':
                remove_orders.append(order_id)
            elif order_info['state'] == 'rejected':
                print(f"Rejected order {order_id} because {order_info['reject_reason']}")
                remove_orders.append(order_id)
        for id in remove_orders:
            del self.open_orders[id]

    def get_cash(self):
        profile = rh.account.build_user_profile()
        return float(profile['cash'])

    def market_open(self):
        """Determine if market is currently open. """
        tz = pytz.timezone('US/Eastern')
        time = dt.datetime.now().astimezone(tz).time()
        open = dt.time(9, 30, 0, tzinfo=tz)
        close = dt.time(16, 0, 0, tzinfo=tz)
        return open < time < close

    def trade(self):
        """Execute trading strategy. """
        while self.market_open():
            prices = rh.stocks.get_latest_price(self.stocks)

            sleep(10)

    





def main():
    trader = RobinHoodBot(RH_USERNAME, RH_PASSWORD, watchlist='bot')
    # for i in range(5):
    #     trader.buy_stock('SOFI', 'limit', price=1, quantity=1)
    print(len(trader.open_orders))
    # print(trader.open_orders)
    print("=======UPDATING")
    # print(trader.cancel_stock_order(list(trader.open_orders.keys())[0]))
    trader.cancel_all_stock_orders()
    sleep(1)
    trader.update_open_orders()
    print(len(trader.open_orders))

if __name__ == '__main__':
    main()
    