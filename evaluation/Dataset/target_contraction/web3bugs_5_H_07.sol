pragma solidity 0.8.3;

contract Utils {

    uint private one = 10**18;
    uint private _10k = 10000;
    uint private _year = 31536000;

    bool private inited;

    address public VADER;
    address public USDV;
    address public ROUTER;
    address public POOLS;
    address public FACTORY;

    function calcAsymmetricShare(uint u, uint U, uint A) public pure returns (uint){
        uint part1 = (u * A);
        uint part2 = ((U * U) * 2);
        uint part3 = ((U * u) * 2);
        uint part4 = (u * u);
        uint numerator = ((part1 * part2) - part3) + part4;
        uint part5 = ((U * U) * U);
        return (numerator / part5);
    }
}
