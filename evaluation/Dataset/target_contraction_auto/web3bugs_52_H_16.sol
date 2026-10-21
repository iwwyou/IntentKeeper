pragma solidity =0.8.9;

contract VaderRouter is IVaderRouter, ProtocolConstants, Ownable {

    using SafeERC20 for IERC20;

    IVaderPoolFactory public immutable factory;

    IVaderReserve public reserve;

    function calculateOutGivenIn(uint256 amountIn, address[] calldata path) external view returns (uint256 amountOut) {
        if (path.length == 2) {
            address nativeAsset = factory.nativeAsset();
            IVaderPool pool = factory.getPool(path[0], path[1]);
            (uint256 nativeReserve, uint256 foreignReserve, ) = pool.getReserves();
            if (path[0] == nativeAsset) {
                return VaderMath.calculateSwap(amountIn, nativeReserve, foreignReserve);
            } else {
                return VaderMath.calculateSwap(amountIn, foreignReserve, nativeReserve);
            }
        } else {
            IVaderPool pool0 = factory.getPool(path[0], path[1]);
            IVaderPool pool1 = factory.getPool(path[1], path[2]);
            (uint256 nativeReserve0, uint256 foreignReserve0, ) = pool0.getReserves();
            (uint256 nativeReserve1, uint256 foreignReserve1, ) = pool1.getReserves();

            return VaderMath.calculateSwap(VaderMath.calculateSwap(amountIn, nativeReserve1, foreignReserve1), foreignReserve0, nativeReserve0);
        }
    }

}
