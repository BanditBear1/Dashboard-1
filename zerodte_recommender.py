import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import math
from scipy.stats import norm

class ZeroDTERecommender:
    def __init__(self):
        self.min_strike_distance = 0.0015  # 0.15% from algorithm
        self.strike_gap = 5  # SPX strikes are 5 points apart
        self.max_strike_width = 5  # From algorithm
        self.ema_window = 5
        self.ema_trend_window = 260
        
    def get_spx_historical_data(self, lookback_days=300):
        """Get SPX historical data for trend calculation"""
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=lookback_days)
            
            # Using SPY as proxy for SPX (multiply by ~10 for SPX equivalent)
            spy = yf.download("SPY", start=start_date, end=end_date, progress=False)
            
            if spy.empty:
                return None
                
            # Convert SPY to SPX equivalent (rough approximation)
            spy['Close'] = spy['Close'] * 10
            
            return spy[['Close']].rename(columns={'Close': 'close'})
            
        except Exception as e:
            print(f"Error fetching historical data: {e}")
            return None
    
    def calculate_trend_score(self, current_spx_price):
        """
        Calculate trend score based on the algorithm's logic:
        trend = np.log(spx_history['close'].rolling(min_periods=1,window=self.ema_window).mean()).diff(1).rolling(window=self.ema_window).sum().iloc[-1]
        """
        try:
            # Get historical data
            hist_data = self.get_spx_historical_data()
            
            if hist_data is None or len(hist_data) < self.ema_trend_window:
                # Fallback to simple calculation if no data
                return {
                    'raw_score': 0.0,
                    'should_trade_long': False,
                    'should_trade_short': False,
                    'vix_level': 18.0,
                    'interpretation': 'No trend data available'
                }
            
            # Limit to trend window
            if len(hist_data) > self.ema_trend_window:
                hist_data = hist_data.iloc[-self.ema_trend_window:]
            
            # Calculate trend score exactly as in algorithm
            ema_close = hist_data['close'].rolling(min_periods=1, window=self.ema_window).mean()
            log_ema = np.log(ema_close)
            diff_log = log_ema.diff(1)
            trend_score = diff_log.rolling(window=self.ema_window).sum().iloc[-1]
            
            # Determine trade direction
            should_trade_long = trend_score > 0
            should_trade_short = trend_score < 0
            
            # Get VIX level
            try:
                vix = yf.download("^VIX", period="1d", progress=False)
                vix_level = vix['Close'].iloc[-1] if not vix.empty else 18.0
            except:
                vix_level = 18.0
            
            # Interpretation
            if trend_score > 0.02:
                interpretation = "Strongly Bullish"
            elif trend_score > 0:
                interpretation = "Weakly Bullish"
            elif trend_score > -0.02:
                interpretation = "Weakly Bearish"
            else:
                interpretation = "Strongly Bearish"
            
            return {
                'raw_score': trend_score,
                'should_trade_long': should_trade_long,
                'should_trade_short': should_trade_short,
                'vix_level': vix_level,
                'interpretation': interpretation
            }
            
        except Exception as e:
            print(f"Error calculating trend: {e}")
            return {
                'raw_score': 0.0,
                'should_trade_long': False,
                'should_trade_short': False,
                'vix_level': 18.0,
                'interpretation': 'Error calculating trend'
            }
    
    def calculate_black_scholes_delta(self, S, K, T, r, sigma, option_type='call'):
        """Calculate Black-Scholes delta"""
        if T <= 0:
            return 1.0 if S > K else 0.0
            
        d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
        
        if option_type == 'call':
            return norm.cdf(d1)
        else:  # put
            return -norm.cdf(-d1)
    
    def get_strike_recommendations(self, spx_price, option_type='put'):
        """Get strike recommendations based on algorithm logic"""
        
        if option_type == 'put':
            # For bull put spreads - strikes below current price
            strike_distance = spx_price * self.min_strike_distance
            target_strike = spx_price - strike_distance
            short_strike = math.floor(target_strike / self.strike_gap) * self.strike_gap
            long_strike = short_strike - self.strike_gap
            
            distance_from_atm = spx_price - short_strike
            
        else:  # call
            # For bear call spreads - strikes above current price
            strike_distance = spx_price * self.min_strike_distance
            target_strike = spx_price + strike_distance
            short_strike = math.ceil(target_strike / self.strike_gap) * self.strike_gap
            long_strike = short_strike + self.strike_gap
            
            distance_from_atm = short_strike - spx_price
        
        # Calculate approximate deltas (using simplified assumptions)
        # T = 1/365 for 0DTE, r = 5%, sigma = 20%
        T = 1/365  # 0DTE
        r = 0.05
        sigma = 0.20
        
        if option_type == 'put':
            short_delta = self.calculate_black_scholes_delta(spx_price, short_strike, T, r, sigma, 'put')
            long_delta = self.calculate_black_scholes_delta(spx_price, long_strike, T, r, sigma, 'put')
        else:
            short_delta = self.calculate_black_scholes_delta(spx_price, short_strike, T, r, sigma, 'call')
            long_delta = self.calculate_black_scholes_delta(spx_price, long_strike, T, r, sigma, 'call')
        
        return {
            'short_strike': short_strike,
            'long_strike': long_strike,
            'short_delta': short_delta,
            'long_delta': long_delta,
            'distance_from_atm': distance_from_atm,
            'strike_width': abs(short_strike - long_strike)
        }
    
    def calculate_spread_metrics(self, short_strike, long_strike, target_credit, max_margin):
        """Calculate spread metrics and contract quantity"""
        
        # Estimated credit per spread (simplified)
        # This would normally come from real options pricing
        strike_width = abs(short_strike - long_strike)
        
        # Rough approximation for 0DTE credit spreads
        estimated_credit_per_spread = strike_width * 30  # $30 per point for 0DTE
        
        # Max loss per spread
        max_loss_per_spread = (strike_width * 100) - estimated_credit_per_spread
        
        # Calculate contracts needed to reach target credit
        contracts_needed = math.ceil(target_credit / estimated_credit_per_spread)
        
        # Check margin requirement
        total_margin_needed = contracts_needed * max_loss_per_spread
        
        if total_margin_needed > max_margin:
            # Reduce contracts to fit margin
            contracts_needed = max_margin // max_loss_per_spread
            contracts_needed = max(1, contracts_needed)
        
        return {
            'estimated_credit': estimated_credit_per_spread,
            'max_loss_per_spread': max_loss_per_spread,
            'contracts_needed': contracts_needed,
            'total_credit': estimated_credit_per_spread * contracts_needed,
            'total_margin': max_loss_per_spread * contracts_needed
        }
    
    def get_trade_recommendations(self, spx_price, target_credit, max_margin):
        """Get complete trade recommendations"""
        
        # Get recommendations for both spread types
        bull_put_rec = self.get_strike_recommendations(spx_price, 'put')
        bear_call_rec = self.get_strike_recommendations(spx_price, 'call')
        
        # Calculate metrics for both
        bull_put_metrics = self.calculate_spread_metrics(
            bull_put_rec['short_strike'], 
            bull_put_rec['long_strike'],
            target_credit,
            max_margin
        )
        
        bear_call_metrics = self.calculate_spread_metrics(
            bear_call_rec['short_strike'],
            bear_call_rec['long_strike'], 
            target_credit,
            max_margin
        )
        
        # Combine recommendations with metrics
        bull_put_spread = {**bull_put_rec, **bull_put_metrics}
        bear_call_spread = {**bear_call_rec, **bear_call_metrics}
        
        return {
            'bull_put_spread': bull_put_spread,
            'bear_call_spread': bear_call_spread,
            'contracts_needed': bull_put_metrics['contracts_needed'],
            'estimated_credit': bull_put_metrics['estimated_credit'],
            'max_loss_per_spread': bull_put_metrics['max_loss_per_spread']
        }
