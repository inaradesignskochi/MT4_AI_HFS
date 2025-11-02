/**
 * AI Scalping System - MT4 Expert Advisor
 * ======================================
 *
 * This Expert Advisor connects to the AI backend to receive trading signals
 * and execute them automatically. It collects real-time tick data and sends
 * it to the backend for analysis.
 *
 * Features:
 * - Real-time tick data collection and transmission
 * - Signal polling from AI backend
 * - Automatic trade execution with risk management
 * - Performance logging and reporting
 *
 * Author: AI Assistant
 * Date: 2025
 *
 * FIXES:
 * 1. Corrected 'WebRequest' overload errors by passing a string variable for result_headers.
 * 2. Fixed OnTrade logic to correctly select closed orders and log them.
 * 3. Added logic to prevent re-logging trades that have already been logged.
 *
 */

//--- Input Parameters
input string   BackendURL      = "https://ai-trading-backend-m1k7.onrender.com";  // Backend server URL
input string   BackendAPIKey   = "production";    // API authentication key
input string   Symbol          = "EURUSD";                               // Trading symbol
input double   LotSize         = 0.01;                                   // Position size
input int      MaxSpread       = 20;                                     // Maximum spread in points
input int      MaxPositions    = 3;                                      // Maximum open positions
input int      Slippage        = 30;                                     // Maximum slippage in points
input int      MagicNumber     = 123456;                                 // EA magic number
input bool     EnableTrading   = false;                                  // Enable/disable trading

//--- Global Variables
int      tickBufferSize     = 500;        // Ticks to buffer before sending
int      signalPollInterval = 500;        // Poll signals every 500ms
datetime lastSignalPoll     = 0;
datetime lastTickSend       = 0;
string   tickData[];
int      tickCount          = 0;
bool     isConnected        = false;
int      lastLoggedTicket   = 0;        // Tracks the last closed ticket we logged

//--- Indicator handles (for technical analysis if needed)
int rsiHandle;
int macdHandle;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
  {
   Print("AI Scalping EA initialized for ", Symbol);

   // Initialize tick data buffer
   ArrayResize(tickData, tickBufferSize);

   // Test backend connection
   if(TestBackendConnection())
     {
      Print("Backend connection successful");
      isConnected = true;
     }
   else
     {
      Print("Backend connection failed - check URL and API key");
      isConnected = false;
     }

   // Find the latest closed ticket to avoid re-logging on restart
   for(int i = OrdersHistoryTotal() - 1; i >= 0; i--)
     {
      if(OrderSelect(i, SELECT_BY_POS, MODE_HISTORY))
        {
         if(OrderSymbol() == Symbol && OrderMagicNumber() == MagicNumber)
           {
            lastLoggedTicket = MathMax(lastLoggedTicket, OrderTicket());
           }
        }
     }
   Print("Last logged ticket set to: ", lastLoggedTicket);

   // Initialize indicators if needed (commented out as not currently used)
   // rsiHandle = iRSI(Symbol, PERIOD_M1, 14, PRICE_CLOSE);
   // macdHandle = iMACD(Symbol, PERIOD_M1, 12, 26, 9, PRICE_CLOSE);

   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   Print("AI Scalping EA deinitialized");

   // Send any remaining tick data
   if(tickCount > 0)
     {
      SendTickData();
     }

   // Clean up
   ArrayFree(tickData);
  }

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
  {
   // Only process if connected
   if(!isConnected)
      return;

   // Collect tick data
   CollectTickData();

   // Only process trading logic if enabled
   if(EnableTrading)
     {
      // Check for signals periodically
      if(GetTickCount() - lastSignalPoll > signalPollInterval)
        {
         CheckForSignals();
         lastSignalPoll = GetTickCount();
        }
     }

   // Send buffered tick data periodically
   if(tickCount >= tickBufferSize || GetTickCount() - lastTickSend > 30000) // 30 seconds
     {
      SendTickData();
     }
  }

//+------------------------------------------------------------------+
//| Collect tick data for transmission to backend                    |
//+------------------------------------------------------------------+
void CollectTickData()
  {
   if(tickCount >= tickBufferSize)
      return;

   // Get current tick data
   double bid = MarketInfo(Symbol, MODE_BID);
   double ask = MarketInfo(Symbol, MODE_ASK);
   double spread = MarketInfo(Symbol, MODE_SPREAD);
   long volume = Volume[0];

   // Create JSON-like string for this tick
   string tickJson = StringFormat(
      "{\"timestamp\":%d,\"bid\":%.5f,\"ask\":%.5f,\"spread\":%.1f,\"volume\":%d}",
      TimeCurrent(),
      bid,
      ask,
      spread,
      volume
      );

   tickData[tickCount] = tickJson;
   tickCount++;

   // Debug output (remove in production)
   //if (tickCount % 100 == 0) {
   //   Print("Collected ", tickCount, " ticks");
   //}
  }

//+------------------------------------------------------------------+
//| Send buffered tick data to backend                               |
//+------------------------------------------------------------------+
void SendTickData()
  {
   if(tickCount == 0)
      return;

   // Create JSON payload
   string payload = "{";
   payload += "\"symbol\":\"" + Symbol + "\",";
   payload += "\"ticks\":[";

   for(int i = 0; i < tickCount; i++)
     {
      payload += tickData[i];
      if(i < tickCount - 1)
         payload += ",";
     }

   payload += "]}";

   // Send to backend
   string url = BackendURL + "/api/ticks";
   string response = SendHttpRequest(url, payload);

   if(response != "")
     {
      // Print("Tick data sent successfully, response: ", response); // Can be noisy
      tickCount = 0; // Reset buffer
      lastTickSend = GetTickCount();
     }
   else
     {
      Print("Failed to send tick data");
     }
  }

//+------------------------------------------------------------------+
//| Check for new trading signals from backend                       |
//+------------------------------------------------------------------+
void CheckForSignals()
  {
   string url = BackendURL + "/api/signals";
   string response = SendHttpRequest(url, ""); // Send GET request

   if(response == "" || StringFind(response, "no_signal") >= 0)
     {
      return; // No signal available
     }

   // Parse signal (simplified JSON parsing)
   string signal = response;

   // Extract signal components (basic string parsing)
   string direction = ExtractValue(signal, "direction");
   double entryPrice = StringToDouble(ExtractValue(signal, "entry_price"));
   double sl = StringToDouble(ExtractValue(signal, "sl"));
   double tp = StringToDouble(ExtractValue(signal, "tp"));
   double confidence = StringToDouble(ExtractValue(signal, "confidence"));

   Print("Received signal: ", direction, " @ ", entryPrice, " (confidence: ", confidence, ")");

   // Validate signal
   if(!ValidateSignal(direction, entryPrice, sl, tp))
     {
      Print("Signal validation failed");
      return;
     }

   // Execute trade
   ExecuteSignal(direction, entryPrice, sl, tp);
  }

//+------------------------------------------------------------------+
//| Validate trading signal                                          |
//+------------------------------------------------------------------+
bool ValidateSignal(string direction, double entryPrice, double sl, double tp)
  {
   // Check spread
   double currentSpread = MarketInfo(Symbol, MODE_SPREAD);
   if(currentSpread > MaxSpread)
     {
      Print("Spread too high: ", currentSpread);
      return false;
     }

   // Check open positions
   int openPositions = CountOpenPositions();
   if(openPositions >= MaxPositions)
     {
      Print("Too many open positions: ", openPositions);
      return false;
     }

   // Check direction validity
   if(direction != "BUY" && direction != "SELL")
     {
      Print("Invalid direction: ", direction);
      return false;
     }

   // Check price levels
   double bid = MarketInfo(Symbol, MODE_BID);
   double ask = MarketInfo(Symbol, MODE_ASK);

   if(direction == "BUY" && entryPrice > ask + (Slippage * Point))
     {
      Print("BUY entry price too high");
      return false;
     }

   if(direction == "SELL" && entryPrice < bid - (Slippage * Point))
     {
      Print("SELL entry price too low");
      return false;
     }

   return true;
  }

//+------------------------------------------------------------------+
//| Execute trading signal                                           |
//+------------------------------------------------------------------+
void ExecuteSignal(string direction, double entryPrice, double sl, double tp)
  {
   int orderType = (direction == "BUY") ? OP_BUY : OP_SELL;
   double price = (direction == "BUY") ? MarketInfo(Symbol, MODE_ASK) : MarketInfo(Symbol, MODE_BID);

   // Submit order
   int ticket = OrderSend(
      Symbol,
      orderType,
      LotSize,
      price,
      Slippage,
      sl,
      tp,
      "AI Scalping Signal",
      MagicNumber,
      0,
      clrBlue
      );

   if(ticket > 0)
     {
      Print("Order executed successfully: ", ticket, " (", direction, ")");

      // Log trade to backend
      LogTradeToBackend(ticket, direction, LotSize, price, sl, tp);
     }
   else
     {
      Print("Order execution failed: ", GetLastError());
     }
  }

//+------------------------------------------------------------------+
//| Count currently open positions                                   |
//+------------------------------------------------------------------+
int CountOpenPositions()
  {
   int count = 0;
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      if(OrderSelect(i, SELECT_BY_POS, MODE_TRADES))
        {
         if(OrderSymbol() == Symbol && OrderMagicNumber() == MagicNumber)
           {
            count++;
           }
        }
     }
   return count;
  }

//+------------------------------------------------------------------+
//| Log executed trade to backend                                    |
//+------------------------------------------------------------------+
void LogTradeToBackend(int ticket, string direction, double lots, double price, double sl, double tp)
  {
   string payload = StringFormat(
      "{\"ticket\":%d,\"symbol\":\"%s\",\"type\":\"%s\",\"lots\":%.2f,\"open_price\":%.5f,\"open_time\":%d,\"sl\":%.5f,\"tp\":%.5f}",
      ticket,
      Symbol,
      direction,
      lots,
      price,
      TimeCurrent(),
      sl,
      tp
      );

   string url = BackendURL + "/api/trades";
   string response = SendHttpRequest(url, payload); // This is a POST

   if(response != "")
     {
      Print("Trade logged to backend successfully");
     }
   else
     {
      Print("Failed to log trade to backend");
     }
  }

//+------------------------------------------------------------------+
//| Send HTTP request to backend                                     |
//+------------------------------------------------------------------+
string SendHttpRequest(string url, string payload)
  {
   string result = "";
   char data[];
   char result_data[];
   string headers = "Content-Type: application/json\r\nAuthorization: Bearer " + BackendAPIKey;
   string result_headers = ""; // <<<--- FIX 1: Variable for response headers

   // For HTTPS, add to allowed URLs in MT4 options
   if(StringFind(url, "https://") == 0)
     {
      // Ensure URL is allowed in MT4 Tools > Options > Expert Advisors
     }

   int timeout = 5000; // 5 seconds

   // Reset last error
   ResetLastError();

   // Convert payload to char array for WebRequest
   int data_size = 0;
   if(payload != "")
     {
      data_size = StringToCharArray(payload, data, 0, StringLen(payload));
     }

   // Send request
   int response_code = 0;
   if(payload == "")
     {
      // GET request
      // Note: data array is empty, which is correct for GET
      response_code = WebRequest("GET", url, headers, timeout, data, result_data, result_headers); // <<<--- FIX 2: Pass result_headers
     }
   else
     {
      // POST request
      response_code = WebRequest("POST", url, headers, timeout, data, result_data, result_headers); // <<<--- FIX 3: Pass result_headers
     }

   // Check for errors
   int error = GetLastError();
   if(error != 0)
     {
      Print("HTTP request failed with error: ", error, " (Code: ", response_code, ")");
      return "";
     }

   if(response_code != 200 && response_code != 201)
     {
      Print("HTTP request returned non-OK status: ", response_code);
     }

   // Convert response back to string
   if(ArraySize(result_data) > 0)
     {
      result = CharArrayToString(result_data, 0, ArraySize(result_data));
     }

   return result;
  }

//+------------------------------------------------------------------+
//| Test backend connection                                          |
//+------------------------------------------------------------------+
bool TestBackendConnection()
  {
   string url = BackendURL + "/api/health";
   string response = SendHttpRequest(url, ""); // Send GET request

   if(response != "" && StringFind(response, "healthy") >= 0)
     {
      return true;
     }

   return false;
  }

//+------------------------------------------------------------------+
//| Extract value from JSON-like string (basic implementation)       |
//+------------------------------------------------------------------+
string ExtractValue(string json, string key)
  {
   string search = "\"" + key + "\":";
   int start = StringFind(json, search);

   if(start == -1)
     {
      // Try without quotes for numbers/booleans
      search = "\"" + key + "\":";
      start = StringFind(json, search);
      if (start == -1) return "";
     }

   start += StringLen(search);

   // Skip leading whitespace or quote
   while(StringSubstr(json, start, 1) == " " || StringSubstr(json, start, 1) == "\"")
     {
      start++;
     }

   // Find the end of the value
   int end = start;

   while(end < StringLen(json))
     {
      string ch = StringSubstr(json, end, 1);

      if(ch == "," || ch == "}")
        {
         break;
        }
      end++;
     }

   string value = StringSubstr(json, start, end - start);

   // Trim trailing whitespace or quote
   while(StringSubstr(value, StringLen(value) - 1, 1) == " " || StringSubstr(value, StringLen(value) - 1, 1) == "\"")
     {
      value = StringSubstr(value, 0, StringLen(value) - 1);
     }

   return value;
  }

//+------------------------------------------------------------------+
//| Expert trade closure handler (FIXED LOGIC)                       |
//+------------------------------------------------------------------+
void OnTrade()
  {
   // Log closed trades to backend
   for(int i = OrdersHistoryTotal() - 1; i >= 0; i--)
     {
      if(OrderSelect(i, SELECT_BY_POS, MODE_HISTORY))
        {
         // Check for a new, closed order for this EA
         if(OrderSymbol() == Symbol && OrderMagicNumber() == MagicNumber && OrderTicket() > lastLoggedTicket)
           {
            // Found a new closed order
            lastLoggedTicket = OrderTicket(); // Update the last logged ticket

            string payload = StringFormat(
               "{\"ticket\":%d,\"close_price\":%.5f,\"profit\":%.2f,\"close_time\":%d,\"comment\":\"Closed by EA\"}",
               OrderTicket(),
               OrderClosePrice(),
               OrderProfit(),
               OrderCloseTime()
               );

            string url = BackendURL + "/api/trades";
            string response = SendHttpRequest(url, payload); // This is a POST

            if(response != "")
              {
               Print("Closed trade logged to backend: ", OrderTicket());
              }
            else
              {
               Print("Failed to log closed trade: ", OrderTicket());
              }

            break; // Only log the most recent new one per event
           }
        }
     }
  }

//+------------------------------------------------------------------+
//| Log closed trade to backend (REMOVED - Merged into OnTrade)      |
//+------------------------------------------------------------------+
// The LogClosedTradeToBackend() function has been removed as its logic
// was merged directly into OnTrade() for safety and correctness.
//+------------------------------------------------------------------+