package optimization

import (
	"fmt"
	"math"
	"runtime"
	"sort"
	"sync"
	"time"

	"github.com/openclaw/skills/quant-researcher/internal/metrics"
	"github.com/openclaw/skills/quant-researcher/pkg/types"
)

// WalkForwardOptimizer implements walk-forward optimization
type WalkForwardOptimizer struct {
	trainSize      int    // Number of periods in training
	testSize       int    // Number of periods in testing
	stepSize       int    // Step size between windows
	numThreads     int
	
	results        []WalkForwardResult
	mu             sync.RWMutex
}

type WalkForwardResult struct {
	WindowIndex    int
	TrainStart     int64
	TrainEnd       int64
	TestStart      int64
	TestEnd        int64
	BestParams     ParameterSet
	TrainMetrics   metrics.PerformanceReport
	TestMetrics    metrics.PerformanceReport
	IS_OOS_Ratio   float64 // In-sample / Out-of-sample ratio
}

type ParameterSet map[string]float64

func NewWalkForwardOptimizer(trainSize, testSize, stepSize int) *WalkForwardOptimizer {
	return &WalkForwardOptimizer{
		trainSize:  trainSize,
		testSize:   testSize,
		stepSize:   stepSize,
		numThreads: runtime.NumCPU(),
		results:    make([]WalkForwardResult, 0),
	}
}

// OptimizationFunction is the function to optimize
type OptimizationFunction func(params ParameterSet, start, end int64) metrics.PerformanceReport

// Run executes the walk-forward optimization
func (wfo *WalkForwardOptimizer) Run(data []types.PricePoint, paramGrid map[string][]float64, optFn OptimizationFunction) ([]WalkForwardResult, error) {
	if len(data) < wfo.trainSize+wfo.testSize {
		return nil, fmt.Errorf("insufficient data for walk-forward optimization")
	}
	
	numWindows := (len(data) - wfo.trainSize - wfo.testSize) / wfo.stepSize
	if numWindows <= 0 {
		return nil, fmt.Errorf("no valid windows with given parameters")
	}
	
	results := make([]WalkForwardResult, numWindows)
	
	// Parallel processing of windows
	var wg sync.WaitGroup
	semaphore := make(chan struct{}, wfo.numThreads)
	
	for i := 0; i < numWindows; i++ {
		wg.Add(1)
		semaphore <- struct{}{}
		
		go func(windowIdx int) {
			defer wg.Done()
			defer func() { <-semaphore }()
			
			trainStart := windowIdx * wfo.stepSize
			trainEnd := trainStart + wfo.trainSize
			testStart := trainEnd
			testEnd := testStart + wfo.testSize
			
			if testEnd > len(data) {
				return
			}
			
			// Grid search on training data
			bestParams, trainMetrics := wfo.gridSearch(
				paramGrid,
				optFn,
				data[trainStart].Timestamp,
				data[trainEnd-1].Timestamp,
			)
			
			// Test on out-of-sample data
			testMetrics := optFn(bestParams, data[testStart].Timestamp, data[testEnd-1].Timestamp)
			
			// Calculate IS/OOS ratio (closer to 1 is better)
			isOOSRatio := 1.0
			if trainMetrics.SharpeRatio != 0 {
				isOOSRatio = testMetrics.SharpeRatio / trainMetrics.SharpeRatio
			}
			
			results[windowIdx] = WalkForwardResult{
				WindowIndex:  windowIdx,
				TrainStart:   data[trainStart].Timestamp,
				TrainEnd:     data[trainEnd-1].Timestamp,
				TestStart:    data[testStart].Timestamp,
				TestEnd:      data[testEnd-1].Timestamp,
				BestParams:   bestParams,
				TrainMetrics: trainMetrics,
				TestMetrics:  testMetrics,
				IS_OOS_Ratio: isOOSRatio,
			}
		}(i)
	}
	
	wg.Wait()
	
	// Filter out empty results
	wfo.results = make([]WalkForwardResult, 0)
	for _, r := range results {
		if r.TrainStart != 0 {
			wfo.results = append(wfo.results, r)
		}
	}
	
	return wfo.results, nil
}

func (wfo *WalkForwardOptimizer) gridSearch(paramGrid map[string][]float64, optFn OptimizationFunction, start, end int64) (ParameterSet, metrics.PerformanceReport) {
	// Generate all parameter combinations
	combinations := wfo.generateCombinations(paramGrid)
	
	bestParams := ParameterSet{}
	bestMetrics := metrics.PerformanceReport{}
	bestScore := -math.MaxFloat64
	
	for _, combo := range combinations {
		metrics := optFn(combo, start, end)
		
		// Score based on Sharpe ratio (can be customized)
		score := metrics.SharpeRatio
		if score > bestScore {
			bestScore = score
			bestParams = combo
			bestMetrics = metrics
		}
	}
	
	return bestParams, bestMetrics
}

func (wfo *WalkForwardOptimizer) generateCombinations(paramGrid map[string][]float64) []ParameterSet {
	if len(paramGrid) == 0 {
		return []ParameterSet{{}}
	}
	
	// Get keys and values
	keys := make([]string, 0, len(paramGrid))
	values := make([][]float64, 0, len(paramGrid))
	for k, v := range paramGrid {
		keys = append(keys, k)
		values = append(values, v)
	}
	
	// Generate combinations recursively
	var combinations []ParameterSet
	var generate func(idx int, current ParameterSet)
	
	generate = func(idx int, current ParameterSet) {
		if idx == len(keys) {
			// Copy current set
			combo := make(ParameterSet)
			for k, v := range current {
				combo[k] = v
			}
			combinations = append(combinations, combo)
			return
		}
		
		for _, v := range values[idx] {
			current[keys[idx]] = v
			generate(idx+1, current)
		}
	}
	
	generate(0, make(ParameterSet))
	return combinations
}

// GetAggregatedResults returns consolidated optimization results
func (wfo *WalkForwardOptimizer) GetAggregatedResults() AggregatedResults {
	wfo.mu.RLock()
	defer wfo.mu.RUnlock()
	
	if len(wfo.results) == 0 {
		return AggregatedResults{}
	}
	
	var totalTrainSharpe, totalTestSharpe, totalIS_OOS float64
	var totalTrainTrades, totalTestTrades int
	
	for _, r := range wfo.results {
		totalTrainSharpe += r.TrainMetrics.SharpeRatio
		totalTestSharpe += r.TestMetrics.SharpeRatio
		totalIS_OOS += r.IS_OOS_Ratio
		totalTrainTrades += r.TrainMetrics.TotalTrades
		totalTestTrades += r.TestMetrics.TotalTrades
	}
	
	n := float64(len(wfo.results))
	
	return AggregatedResults{
		NumWindows:         len(wfo.results),
		AvgTrainSharpe:     totalTrainSharpe / n,
		AvgTestSharpe:      totalTestSharpe / n,
		AvgIS_OOS_Ratio:    totalIS_OOS / n,
		TotalTrainTrades:   totalTrainTrades,
		TotalTestTrades:    totalTestTrades,
		RobustnessScore:    wfo.calculateRobustness(),
	}
}

func (wfo *WalkForwardOptimizer) calculateRobustness() float64 {
	if len(wfo.results) == 0 {
		return 0
	}
	
	// Robustness based on consistency of results across windows
	sharpeRatios := make([]float64, len(wfo.results))
	for i, r := range wfo.results {
		sharpeRatios[i] = r.TestMetrics.SharpeRatio
	}
	
	// Calculate coefficient of variation (lower is more robust)
	mean, stdDev := calculateMeanStdDev(sharpeRatios)
	if mean == 0 {
		return 0
	}
	
	cv := stdDev / math.Abs(mean)
	// Convert to 0-1 score (1 = most robust)
	robustness := 1.0 / (1.0 + cv)
	
	return robustness
}

type AggregatedResults struct {
	NumWindows      int
	AvgTrainSharpe  float64
	AvgTestSharpe   float64
	AvgIS_OOS_Ratio float64
	TotalTrainTrades int
	TotalTestTrades int
	RobustnessScore float64
}

// MonteCarloSimulator performs Monte Carlo simulation for strategy validation
type MonteCarloSimulator struct {
	numSimulations int
	confidenceLevel float64
}

func NewMonteCarloSimulator(numSimulations int, confidenceLevel float64) *MonteCarloSimulator {
	if confidenceLevel <= 0 || confidenceLevel >= 1 {
		confidenceLevel = 0.95
	}
	return &MonteCarloSimulator{
		numSimulations:  numSimulations,
		confidenceLevel: confidenceLevel,
	}
}

// SimulationResult holds Monte Carlo simulation results
type SimulationResult struct {
	OriginalSharpe      float64
	MeanSharpe          float64
	StdDevSharpe        float64
	WorstSharpe         float64
	BestSharpe          float64
	ConfidenceInterval  [2]float64
	ProbabilityOfProfit float64
	MaxDrawdown95       float64
	ValueAtRisk95       float64
	SimulatedCurves     [][]float64
}

// Run executes Monte Carlo simulation on trade returns
func (mc *MonteCarloSimulator) Run(returns []float64, initialEquity float64) SimulationResult {
	if len(returns) == 0 {
		return SimulationResult{}
	}
	
	// Calculate original metrics
	originalSharpe := calculateSharpeFromReturns(returns)
	
	// Run simulations
	sharpeRatios := make([]float64, mc.numSimulations)
	finalEquities := make([]float64, mc.numSimulations)
	maxDrawdowns := make([]float64, mc.numSimulations)
	simulatedCurves := make([][]float64, mc.numSimulations)
	
	for i := 0; i < mc.numSimulations; i++ {
		// Bootstrap sample with replacement
		simulatedReturns := mc.bootstrapSample(returns)
		
		// Calculate equity curve
		equityCurve := mc.calculateEquityCurve(simulatedReturns, initialEquity)
		simulatedCurves[i] = equityCurve
		
		// Calculate metrics
		sharpeRatios[i] = calculateSharpeFromReturns(simulatedReturns)
		finalEquities[i] = equityCurve[len(equityCurve)-1]
		maxDrawdowns[i] = calculateMaxDrawdown(equityCurve)
	}
	
	// Calculate statistics
	meanSharpe, stdDevSharpe := calculateMeanStdDev(sharpeRatios)
	sort.Float64s(sharpeRatios)
	worstSharpe := sharpeRatios[0]
	bestSharpe := sharpeRatios[len(sharpeRatios)-1]
	
	// Confidence interval
	alpha := 1.0 - mc.confidenceLevel
	lowerIdx := int(alpha/2 * float64(len(sharpeRatios)))
	upperIdx := int((1.0-alpha/2) * float64(len(sharpeRatios)))
	ci := [2]float64{sharpeRatios[lowerIdx], sharpeRatios[upperIdx]}
	
	// Probability of profit
	profitable := 0
	for _, eq := range finalEquities {
		if eq > initialEquity {
			profitable++
		}
	}
	probProfit := float64(profitable) / float64(len(finalEquities))
	
	// Max drawdown at 95%
	sort.Float64s(maxDrawdowns)
	dd95Idx := int(0.95 * float64(len(maxDrawdowns)))
	maxDD95 := maxDrawdowns[dd95Idx]
	
	return SimulationResult{
		OriginalSharpe:      originalSharpe,
		MeanSharpe:          meanSharpe,
		StdDevSharpe:        stdDevSharpe,
		WorstSharpe:         worstSharpe,
		BestSharpe:          bestSharpe,
		ConfidenceInterval:  ci,
		ProbabilityOfProfit: probProfit,
		MaxDrawdown95:       maxDD95,
		SimulatedCurves:     simulatedCurves,
	}
}

func (mc *MonteCarloSimulator) bootstrapSample(returns []float64) []float64 {
	sample := make([]float64, len(returns))
	for i := range sample {
		idx := int(math.Floor(float64(len(returns)) * mc.randomFloat()))
		if idx >= len(returns) {
			idx = len(returns) - 1
		}
		sample[i] = returns[idx]
	}
	return sample
}

func (mc *MonteCarloSimulator) randomFloat() float64 {
	// Simple random number generation (replace with better PRNG for production)
	return float64(time.Now().UnixNano()%1000000) / 1000000.0
}

func (mc *MonteCarloSimulator) calculateEquityCurve(returns []float64, initialEquity float64) []float64 {
	equity := make([]float64, len(returns)+1)
	equity[0] = initialEquity
	
	for i, r := range returns {
		equity[i+1] = equity[i] * (1.0 + r)
	}
	
	return equity
}

// Helper functions
func calculateMeanStdDev(values []float64) (mean, stdDev float64) {
	if len(values) == 0 {
		return 0, 0
	}
	
	for _, v := range values {
		mean += v
	}
	mean /= float64(len(values))
	
	var variance float64
	for _, v := range values {
		diff := v - mean
		variance += diff * diff
	}
	stdDev = math.Sqrt(variance / float64(len(values)))
	
	return mean, stdDev
}

func calculateSharpeFromReturns(returns []float64) float64 {
	if len(returns) == 0 {
		return 0
	}
	
	mean, stdDev := calculateMeanStdDev(returns)
	if stdDev == 0 {
		return 0
	}
	
	return mean / stdDev * math.Sqrt(252.0) // Annualized
}

func calculateMaxDrawdown(equity []float64) float64 {
	if len(equity) == 0 {
		return 0
	}
	
	peak := equity[0]
	maxDD := 0.0
	
	for _, e := range equity {
		if e > peak {
			peak = e
		}
		
		drawdown := (peak - e) / peak
		if drawdown > maxDD {
			maxDD = drawdown
		}
	}
	
	return maxDD
}