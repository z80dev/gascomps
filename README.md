# gas comparisons between solady and vyper

`pip install eth-ape ape-huff`

`ape plugins install .`

`ape test --gas`


# output

```
================================= Gas Profile ==================================
                        SoladyToken Gas                         
                                                                
  Method         Times called    Min.    Max.    Mean   Median  
 ────────────────────────────────────────────────────────────── 
  allowance                 3   24521   24521   24521    24521  
  approve                   1   24441   24441   24441    24441  
  balanceOf                 6   23974   23974   23974    23974  
  transfer                  2   29500   29500   29500    29500  
  transferFrom              1   14112   14112   14112    14112  
                                                                
                         VyperToken Gas                         
                                                                
  Method         Times called    Min.    Max.    Mean   Median  
 ────────────────────────────────────────────────────────────── 
  allowance                 3   24340   24340   24340    24340  
  approve                   1   24316   24316   24316    24316  
  balanceOf                 6   23840   23840   23840    23840  
  transfer                  2   29669   29669   29669    29669  
  transferFrom              1   14471   14471   14471    14471  
                                                                
                          OZToken Gas                           
                                                                
  Method         Times called    Min.    Max.    Mean   Median  
 ────────────────────────────────────────────────────────────── 
  allowance                 3   24645   24645   24645    24645  
  approve                   1   24735   24735   24735    24735  
  balanceOf                 6   23991   23991   23991    23991  
  transfer                  2   30004   30004   30004    30004  
  transferFrom              1   14878   14878   14878    14878  
                                                                
                           WETH9 Gas                            
                                                                
  Method         Times called    Min.    Max.    Mean   Median  
 ────────────────────────────────────────────────────────────── 
  0x                        1   23632   23632   23632    23632  
  allowance                 3   24234   24234   24234    24234  
  approve                   1   24297   24297   24297    24297  
  balanceOf                 6   23801   23801   23801    23801  
  transfer                  2   29480   29480   29480    29480  
  transferFrom              1   15544   15544   15544    15544  
                                                                

============================== 1 passed in 1.87s ===============================
INFO: Stopping 'anvil' process.

```

