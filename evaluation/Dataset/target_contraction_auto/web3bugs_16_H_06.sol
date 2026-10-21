pragma solidity ^0.8.0;

contract GasOracle is IOracle, Ownable {
    using LibMath for uint256;
    IChainlinkOracle public gasOracle;
    IChainlinkOracle public priceOracle;
    uint8 public override decimals = 18;
    uint256 private constant MAX_DECIMALS = 18;

    function latestAnswer() external view override returns (uint256) {
        uint256 gasPrice = uint256(gasOracle.latestAnswer());
        uint256 ethPrice = uint256(priceOracle.latestAnswer());

        uint256 result = PRBMathUD60x18.mul(gasPrice, ethPrice);
        return result;
    }

}
