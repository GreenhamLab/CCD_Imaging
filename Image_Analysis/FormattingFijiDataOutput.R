### Reshaping Fiji output files ###

## Set up the environment
setwd("~/Desktop/LUC_Imaging")

require(tidyverse)


## Bring in the raw data file
rawDat = read.csv("RawData.csv", header = FALSE)


## Create a vector to grab sequential chunks of rows to move into columns
  # Change input such that `each` = #observations (plants plus blanks) and `rep` = 1 to # tps (columns)
n = rep(1:60, each = 35)

  # Split the raw data in n number of pieces and merge into a dataframe
dat = as.data.frame(split(rawDat, n))
  # Remove the redundant Plant IDs
dat = dat %>% select(!(contains(".V1")))
  # Specify the number of blanks - 1. The sample data has 3 blanks.
numBlanks = 2
  # Pull out the blanks to average by ZT
avgBlank = dat[(nrow(dat) - numBlanks):nrow(dat), ]
avgBlank = colMeans(avgBlank)
  # remove the uninformative column names
avgBlank = unname(avgBlank)
  # Remove the blanks from the original df and transpose to match avgBlank
dat2 = dat[-c((nrow(dat) - numBlanks):nrow(dat)), ]
dat2 = data.frame(t(dat2))
  # Subtract the blank from every cell 
LUC_data = dat2-avgBlank


## Clean up
  # make a vector of ZTs (first to last ZT and how many hours in between each)
ZT = seq(from = 2, to = 120, by = 2)
LUC_data$ZT = ZT
  # Move ZTs to the first column so it's easier to find in BioDare
LUC_data = LUC_data %>% relocate(ZT)
  # Rownames are meaningless, set to NULL to avoid potential confusion
rownames(LUC_data) = NULL

# Fix the column names; we specify Genotype but you may want to include Treatment or Conditions
  # we have 32 CCA1_Luc plants
colnames(LUC_data) =  c(paste("ZT"),paste(rep("CCA1", 32)))

## Save
write.csv(LUC_data, file = "BioDare_Formatted_Data.csv", row.names = FALSE)



