// SPDX-License-Identifier: MIT

pragma solidity ^0.8.4;

import "@openzeppelin/token/ERC20/ERC20.sol";

contract OZToken is ERC20 {
    constructor() ERC20("OZToken", "OZ") {
        _mint(msg.sender, 1000000000000000000000000000);
    }
}
