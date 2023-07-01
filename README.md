# gas comparisons between solady and vyper

`pip install eth-ape ape-huff dasy ape-dasy`

`ape plugins install .`

`ape test --gas`

# Results By Function

**approve Gas**

| Contract   | Min.  | Max.  | Mean  |
|------------|-------|-------|-------|
| WETH9      | 4257  | 24157 | 16757 |
| DasyToken  | 4416  | 24316 | 16916 |
| VyperToken | 4416  | 24316 | 16916 |
| SoladyToken| 4541  | 24441 | 17041 |
| OZToken    | 4835  | 24735 | 17335 |

**balanceOf Gas**

| Contract   | Min. | Max. | Mean  |
|------------|------|------|-------|
| WETH9      | 23773| 23773| 23773 |
| DasyToken  | 23794| 23794| 23794 |
| VyperToken | 23840| 23840| 23840 |
| SoladyToken| 23974| 23974| 23974 |
| OZToken    | 23991| 23991| 23991 |

**transfer Gas**

| Contract   | Min. | Max.  | Mean  |
|------------|------|-------|-------|
| WETH9      | 12110| 29210 | 14960 |
| SoladyToken| 12400| 29500 | 15250 |
| DasyToken  | 12454| 29554 | 15304 |
| VyperToken | 12569| 29669 | 15419 |
| OZToken    | 12904| 30004 | 15754 |

**transferFrom Gas**

| Contract   | Min. | Max.  | Mean  |
|------------|------|-------|-------|
| SoladyToken| 14112| 17639 | 16127 |
| DasyToken  | 14379| 17973 | 16433 |
| VyperToken | 14471| 18088 | 16538 |
| OZToken    | 14878| 18597 | 17003 |
| WETH9      | 15257| 19071 | 17436 |

Finally, here are the contracts sorted by increasing total average gas usage:

1. SoladyToken (72392 gas)
2. DasyToken (72447 gas)
3. VyperToken (72713 gas)
4. WETH9 (72926 gas)
5. OZToken (74083 gas)

I've calculated the total gas usage for each contract by summing the mean gas usages of all functions for each contract.

# raw output

```
================================= Gas Profile ==================================
                        SoladyToken Gas                         
                                                                
  Method         Times called    Min.    Max.    Mean   Median  
 ────────────────────────────────────────────────────────────── 
  approve                  50    4541   24441   17041    24441  
  balanceOf                 3   23974   23974   23974    23974  
  transfer                 12   12400   29500   15250    12400  
  transferFrom             70   14112   17639   16127    17639  
                                                                
                         VyperToken Gas                         
                                                                
  Method         Times called    Min.    Max.    Mean   Median  
 ────────────────────────────────────────────────────────────── 
  approve                  50    4416   24316   16916    24316  
  balanceOf                 3   23840   23840   23840    23840  
  transfer                 12   12569   29669   15419    12569  
  transferFrom             70   14471   18088   16538    18088  
                                                                
                          OZToken Gas                           
                                                                
  Method         Times called    Min.    Max.    Mean   Median  
 ────────────────────────────────────────────────────────────── 
  approve                  50    4835   24735   17335    24735  
  balanceOf                 3   23991   23991   23991    23991  
  transfer                 12   12904   30004   15754    12904  
  transferFrom             70   14878   18597   17003    18597  
                                                                
                           WETH9 Gas                            
                                                                
  Method         Times called    Min.    Max.    Mean   Median  
 ────────────────────────────────────────────────────────────── 
  0x                        1   46133   46133   46133    46133  
  approve                  50    4257   24157   16757    24157  
  balanceOf                 3   23773   23773   23773    23773  
  transfer                 12   12110   29210   14960    12110  
  transferFrom             70   15257   19071   17436    19071  
                                                                
                         DasyToken Gas                          
                                                                
  Method         Times called    Min.    Max.    Mean   Median  
 ────────────────────────────────────────────────────────────── 
  approve                  50    4416   24316   16916    24316  
  balanceOf                 3   23794   23794   23794    23794  
  transfer                 12   12454   29554   15304    12454  
  transferFrom             70   14379   17973   16433    17973  
                                                                

============================== 1 passed in 37.02s ==============================
INFO: Stopping 'anvil' process.

```
