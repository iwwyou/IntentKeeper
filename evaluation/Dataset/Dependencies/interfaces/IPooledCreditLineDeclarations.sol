pragma solidity 0.7.6;

interface IPooledCreditLineDeclarations is IPooledCreditLineEnums {
    struct Request {
        uint256 collateralRatio;
        uint256 duration;
        address lenderVerifier;
        uint256 defaultGracePeriod;
        uint256 gracePenaltyRate;
        uint256 collectionPeriod;
        uint256 minBorrowAmount;
        uint128 borrowLimit;
        uint128 borrowRate;
        address collateralAsset;
        address borrowAssetStrategy;
        address collateralAssetStrategy;
        address borrowAsset;
        address borrowerVerifier;
        bool areTokensTransferable;
    }

    struct PooledCreditLineVariables {
        PooledCreditLineStatus status;
        uint256 principal;
        uint256 totalInterestRepaid;
        uint256 lastPrincipalUpdateTime;
        uint256 interestAccruedTillLastPrincipalUpdate;
    }

    struct PooledCreditLineConstants {
        uint128 borrowLimit;
        uint128 borrowRate;
        uint256 idealCollateralRatio;
        address borrower;
        address borrowAsset;
        address collateralAsset;
        uint256 startsAt;
        uint256 endsAt;
        uint256 defaultsAt;
        address borrowAssetStrategy;
        address collateralAssetStrategy;
        uint256 gracePenaltyRate;
    }
}
