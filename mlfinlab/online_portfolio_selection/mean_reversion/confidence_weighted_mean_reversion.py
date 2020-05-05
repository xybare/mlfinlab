# pylint: disable=missing-module-docstring
import numpy as np
from scipy.stats import norm
from mlfinlab.online_portfolio_selection.online_portfolio_selection import OLPS


class ConfidenceWeightedMeanReversion(OLPS):
    """
    This class implements the Confidence Weighted Mean Reversion strategy. It is reproduced with
    modification from the following paper:
    `Li, B., Hoi, S.C., Zhao, P. & Gopalkrishnan, V.. (2011). Confidence Weighted Mean Reversion
    Strategy for On-Line Portfolio Selection. Proceedings of the Fourteenth International
    Conference on Artificial Intelligence and Statistics, in PMLR 15:434-442.
    <https://ink.library.smu.edu.sg/cgi/viewcontent.cgi?article=3292&context=sis_research>`_

    Confidence Weighted Mean Reversion exploits both the popular mean reversion techniques and
    second-order information to model weights as a gaussian distribution.
    """

    def __init__(self, confidence, epsilon, method='var'):
        """
        Initializes Confidence Weighted Mean Reversion with the given confidence, epsilon, and method.

        :param confidence: (float) Confidence parameter. Must be between 0 and 1.
        :param epsilon: (float) Mean reversion parameter. Must be between 0 and 1.
        :param method: (string) Variance update method. Choose 'var' for variance and 'sd' for
                                standard deviation
        """
        self.confidence = confidence
        self.theta = None
        self.epsilon = epsilon
        self.method = method
        self.sigma = None  # (np.array) Variance of the portfolio distribution.
        self.mu_dist = None  # (np.array) Mean of the portfolio distribution.
        super().__init__()

    def _initialize(self, asset_prices, weights, resample_by):
        """
        Initializes the important variables for the object.

        :param asset_prices: (pd.DataFrame) Historical asset prices.
        :param weights: (list/np.array/pd.Dataframe) Initial weights set by the user.
        :param resample_by: (str) Specifies how to resample the prices.
        """
        super(ConfidenceWeightedMeanReversion, self)._initialize(asset_prices, weights, resample_by)

        # Check that epsilon value is correct.
        if self.epsilon < 0 or self.epsilon > 1:
            raise ValueError("Epsilon values must be between 0 and 1.")

        # Check that the confidence value is correct.
        if self.confidence < 0 or self.confidence > 1:
            raise ValueError("Confidence values must be between 0 and 1.")

        # If confidence is valid, set theta value.
        self.theta = norm.ppf(self.confidence)

        # Check that the given method is correct.
        if self.method != 'var' and self.method != 'sd':
            raise ValueError("Method must be either 'var' or 'sd'.")

    def _update_weight(self, time):
        """
        Predicts the next time's portfolio weight.

        :param time: (int) Current time period.
        :return new_weights: (np.array) Predicted weights.
        """
        # Set current relative returns.
        curr_relative_return = self.relative_return[[time]]
        # Calculate dot product of relative returns and current weights.
        new_m = np.dot(curr_relative_return, self.weights)[0]
        # Calculate the variance of current relative returns.
        new_v = np.dot(np.dot(curr_relative_return, self.sigma), curr_relative_return.T)[0][0]
        # Calculate weighted variance.
        new_w = np.dot(np.dot(curr_relative_return, self.sigma), np.identity(self.number_of_assets))[0]
        # Calculate weighted average.
        mean_x = np.diag(self.sigma) / np.trace(self.sigma)

        # Expression to speed up calculations.
        expn = new_v - np.dot(mean_x, new_w) + self.theta ** 2 * new_v / 2

        # Calculate constants for quadratic equation.
        quad_a = expn ** 2 - self.theta ** 4 * new_v ** 2 / 4
        quad_b = 2 * (self.epsilon - new_m) * expn
        quad_c = (self.epsilon - new_m) ** 2 - self.theta ** 2 * new_v

        # Calculate lagrangian.
        if quad_b ** 2 - 4 * quad_a * quad_c < 0:
            lambd = np.max([-quad_c/quad_b, 0])
        else:
            lambd = np.max([(-quad_b + np.sqrt(quad_b ** 2 - 4 * quad_a * quad_c)) / (2 * quad_a),
                            (-quad_b - np.sqrt(quad_b ** 2 - 4 * quad_a * quad_c)) / (2 * quad_a),
                            -quad_c / quad_b, 0])
        # Update mu.
        self.mu_dist -= lambd * np.dot(curr_relative_return - mean_x, self.sigma).reshape((self.number_of_assets,))

        if self.method == 'sd':
            # Component for new variance calculation.
            sqrt_u = (-lambd * self.theta * new_v + np.sqrt(lambd ** 2 * self.theta ** 2 * new_v ** 2 + 4 * new_v)) / 2
            # Update variance.
            self.sigma = np.linalg.pinv(np.linalg.pinv(self.sigma) + lambd * self.theta / sqrt_u * np.diag(curr_relative_return) ** 2)
        if self.method == 'var':
            # Update variance.
            self.sigma = np.linalg.pinv(
                np.linalg.pinv(self.sigma) + 2 * lambd * self.theta * np.diag(curr_relative_return) ** 2)
        # Normalize variance.
        self.sigma /= new_m * np.trace(self.sigma)
        # Simplex projection.
        self.mu_dist = self._simplex_projection(self.mu_dist)
        new_weights = self.mu_dist
        return new_weights

    def _first_weight(self, weights):
        """
        Returns the first weight of the given portfolio. If the first weight is not given,
        initialize weights to uniform weights.

        :param weights: (list/np.array/pd.Dataframe) Initial weights set by the user.
        :return (weights): (np.array) First portfolio weight.
        """
        # Set sigma, the variance of the portfolio distribution.
        self.sigma = np.identity(self.number_of_assets) / (self.number_of_assets ** 2)

        # If no weights are given, return uniform weights.
        if weights is None:
            weights = self._uniform_weight()

        # Set mu, the mean of the portfolio distribution.
        self.mu_dist = weights
        return weights
