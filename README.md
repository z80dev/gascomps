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
  0x                        1   46133   46133   46133    46133  
  allowance                 3   24178   24178   24178    24178  
  approve                   1   24157   24157   24157    24157  
  balanceOf                 6   23773   23773   23773    23773  
  transfer                  2   29210   29210   29210    29210  
  transferFrom              1   15257   15257   15257    15257  
                                                                

============================== 1 passed in 1.98s ===============================
INFO: Stopping 'anvil' process.

```
