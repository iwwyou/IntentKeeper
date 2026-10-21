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

    function getSlipAdustment(uint b, uint B, uint t, uint T) public view returns (uint){
        uint part1 = B * t;
        uint part2 = b * T;
        uint part3 = (b * 2) + B;
        uint part4 = t + T;
        uint numerator;
        if(part1 > part2){
            numerator = (part1 - part2);
        } else {
            numerator = (part2 - part1);
        }
        uint denominator = (part3 * part4);
        return one - (numerator * one) / denominator;
    }

    function calcLiquidityUnits(uint b, uint B, uint t, uint T, uint P) external view returns (uint){
        if(P == 0){
            return b;
        } else {
            uint slipAdjustment = getSlipAdustment(b, B, t, T);
            uint part1 = (t * B);
            uint part2 = (T * b);
            uint part3 = (T * B) * 2;
            uint _units = (((P * part1) + part2) / part3);
            return (_units * slipAdjustment) / one;
        }
    }
}
